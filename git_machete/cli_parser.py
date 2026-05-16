"""Command-line argument parser for git-machete.

A small hand-rolled parser layered on top of `getopt.gnu_getopt`.
The heavy-lifting features (typo suggestions, scoped close-match hints, hidden-but-still-accepted choices,
required-positional listings, ...) all live here; `getopt` is only used for the option-parsing primitive.

The spec types this parser operates on, plus the actual catalog of git-machete commands
(`COMMANDS`, `COMMON_OPTIONS`, ...) live in `cli_commands.py`.
This file imports them and runs the parsing pass; `cli.py` is the single external caller, via `parse_cmdline(argv)`.
"""

import difflib
import getopt
import itertools
import sys
from typing import Any, Dict, Iterable, List, NoReturn, Optional, Tuple

from git_machete.cli_commands import (COMMAND_BY_NAME_OR_ALIAS, COMMON_OPTIONS,
                                      CommandSpec, MutexGroup, OptSpec,
                                      ParsedCmd, PositionalSpec,
                                      SubcommandSpec)
from git_machete.utils import markup, terminal
from git_machete.utils.exceptions import ExitCode, MacheteException

_CLOSE_MATCH_CUTOFF = 0.6
_MAX_SUGGESTIONS = 3


# ────────────────────────────────────────────────────────────────────────────
# Parsing
# ────────────────────────────────────────────────────────────────────────────


def parse_cmdline(argv: List[str]) -> ParsedCmd:
    """Parse `argv` into a `ParsedCmd` or exit with an argument error."""
    direct, pass_through = _split_on_dashdash(argv)

    # Locate the command in `direct`. Anything before it must be a common-option flag;
    # anything after is parsed against the merged spec (common + command-specific + selected-subcommand).
    cmd_pos = _find_command_position(direct)

    if cmd_pos is None:
        # Either there are no positionals at all (`git machete --help`) or the only "positional" we'd see is an unknown flag (e.g. `-q`).
        # Validate against common options only and return.
        opts, _, unknowns = _scan(direct, COMMON_OPTIONS)
        _apply_color_setting(opts.get("color"))
        if unknowns:
            _fail_unrecognized(unknowns, command=None)
        return ParsedCmd(command=None, opts=opts, positionals={}, pass_through=pass_through)

    cmd_name_typed = direct[cmd_pos]
    cmd = COMMAND_BY_NAME_OR_ALIAS.get(cmd_name_typed)
    if cmd is None:
        _fail_invalid_command(cmd_name_typed)

    # Build the union of every option this command may accept on any subcommand:
    # needed so the option parser knows what's syntactically valid.
    # We later cross-check each used option against the SELECTED subcommand
    # and emit a friendlier "only valid with X subcommand" error for the legal-but-not-here case.
    all_command_options = _collect_all_options(cmd)
    merged_options = COMMON_OPTIONS + all_command_options
    other_args = direct[:cmd_pos] + direct[cmd_pos + 1:]
    opts, positionals, unknowns = _scan(other_args, merged_options)
    # Apply `--color` before any downstream validation step that might construct a `MacheteException`:
    # the exception captures the current `markup.use_ansi_escapes_in_*` values at __init__ time and rendering is one-shot.
    _apply_color_setting(opts.get("color"))
    if unknowns:
        _fail_unrecognized(unknowns, command=cmd.name)

    # `--help` and `--version` short-circuit positional/mutex validation so that
    # e.g. `git machete completion --help` prints the completion help page instead of complaining about the missing `shell` positional.
    if "help" in opts or "version" in opts:
        return ParsedCmd(command=cmd.name, opts=opts, positionals={}, pass_through=pass_through)

    effective_positionals = _effective_positionals(cmd)
    parsed_positionals = _validate_positionals(positionals, cmd, effective_positionals)

    selected_subcommand = _selected_subcommand(cmd, parsed_positionals)
    if cmd.subcommands and selected_subcommand is not None:
        _validate_subcommand_restrictions(opts, parsed_positionals, cmd, selected_subcommand)

    effective_mutex = cmd.mutex_groups + (
        selected_subcommand.mutex_groups if selected_subcommand is not None else ())
    _validate_mutex_groups(opts, effective_mutex, merged_options)

    return ParsedCmd(
        command=cmd.name,
        opts=opts,
        positionals=parsed_positionals,
        pass_through=pass_through,
    )


def _collect_all_options(cmd: CommandSpec) -> Tuple[OptSpec, ...]:
    seen: Dict[str, OptSpec] = {o.storage_key: o for o in cmd.options}
    for sub in cmd.subcommands:
        for o in sub.options:
            seen.setdefault(o.storage_key, o)
    return tuple(seen.values())


def _effective_positionals(cmd: CommandSpec) -> Tuple[PositionalSpec, ...]:
    """Build the final positional list for this command, prepending a synthetic subcommand selector when `cmd.subcommands` is non-empty."""
    if not cmd.subcommands:
        return cmd.positionals
    selector = PositionalSpec(
        name=cmd.subcommand_positional_name,
        display_name=cmd.subcommand_display_label,
        choices=tuple(s.name for s in cmd.subcommands),
        hidden_choices=frozenset(s.name for s in cmd.subcommands if s.hidden),
    )
    return (selector,) + cmd.positionals


def _selected_subcommand(
        cmd: CommandSpec,
        parsed_positionals: Dict[str, Any],
) -> Optional[SubcommandSpec]:
    if not cmd.subcommands:
        return None
    name = parsed_positionals.get(cmd.subcommand_positional_name)
    if name is None:  # pragma: no cover
        # Unreachable in practice: `_validate_positionals` rejects a missing required subcommand positional before this function is called.
        return None
    return next((s for s in cmd.subcommands if s.name == name), None)


# --- Internal helpers ------------------------------------------------------


def _split_on_dashdash(argv: List[str]) -> Tuple[List[str], List[str]]:
    direct = list(itertools.takewhile(lambda a: a != "--", argv))
    after = list(itertools.dropwhile(lambda a: a != "--", argv))
    pass_through = after[1:] if after else []
    return direct, pass_through


def _find_command_position(direct: List[str]) -> Optional[int]:
    """Walk `direct`, skipping common-option flags, and return the index of the first positional token.

    `None` if there is no positional at all (or if we hit something option-looking we can't classify -
    in which case the parser will surface it as an unknown flag below).
    """
    common_long = {o.long for o in COMMON_OPTIONS if o.long}
    common_short = {o.short for o in COMMON_OPTIONS if o.short}
    i = 0
    while i < len(direct):
        a = direct[i]
        if a.startswith("--"):
            name = a[2:].split("=", 1)[0]
            if name in common_long:
                # None of the common options take a value, so just step over.
                i += 1
                continue
            # Unknown long option in the top-level segment - bail out without picking a command.
            # The unknown-flag scan downstream will turn this into a proper error.
            return None
        if a.startswith("-") and len(a) > 1:
            short = a[1:]
            # Single-letter short → check against the common short flags;
            # longer `-XXX` (e.g. `-gs`) is by definition not a common short flag, so bail out for the same reason as above.
            if len(short) == 1 and short in common_short:
                i += 1
                continue
            return None
        return i
    return None


def _scan(
        argv: List[str],
        options: Iterable[OptSpec],
) -> Tuple[Dict[str, str], List[str], List[str]]:
    """The actual option scanner.

    Uses `getopt.gnu_getopt` for the happy path
    (so we inherit its handling of `--long=value`, `--long value`, `-x value`, `-xvalue`, combined short flags, ...).
    On `GetoptError` we fall back to a single-pass manual sweep that collects EVERY unknown flag (and its trailing value, if any)
    so the user sees them all at once - rather than getting picked off one by one as they fix typos.

    Returns `(opts, positionals, unknown_flag_tokens)`.
    `unknown_flag_tokens` is the raw arg list as the user typed it (e.g. `["--srart-from", "foo"]`)
    so the error formatter can re-emit it verbatim.
    """
    long_specs: Dict[str, OptSpec] = {o.long: o for o in options if o.long}
    short_specs: Dict[str, OptSpec] = {o.short: o for o in options if o.short}

    # Build getopt-format short/long strings.
    short_str = "".join(
        s + (":" if spec.takes_value else "")
        for s, spec in short_specs.items()
    )
    long_list = [
        (lng + "=" if spec.takes_value else lng)
        for lng, spec in long_specs.items()
    ]

    # `getopt` treats `-b=foo` as `-b` with value `"=foo"`, but we want `-b foo` semantics
    # so callers can write either `-b foo`, `-bfoo` or `-b=foo` interchangeably.
    # Normalize the `-X=value` form here.
    normalized_argv = []
    for a in argv:
        if (len(a) >= 4 and a.startswith("-") and not a.startswith("--") and
                a[1] in short_specs and short_specs[a[1]].takes_value and
                a[2] == "="):
            normalized_argv.append(a[:2])
            normalized_argv.append(a[3:])
        else:
            normalized_argv.append(a)

    try:
        pairs, positionals = getopt.gnu_getopt(normalized_argv, short_str, long_list)
    except getopt.GetoptError as e:
        # Recover all unknowns ourselves, so the error message lists every bad token at once.
        unknown_tokens = _collect_unknown_tokens(argv, long_specs, short_specs)
        if unknown_tokens:
            return {}, [], unknown_tokens
        # getopt raised for some other reason
        # (typically "option X requires argument" when the user passes a value-taking flag with no value after it).
        # Surface getopt's own message as a regular argument error rather than letting an uncaught `GetoptError` propagate.
        _argument_error(str(e))

    opts: Dict[str, str] = {}
    for raw_flag, raw_value in pairs:
        spec = (long_specs[raw_flag[2:]] if raw_flag.startswith("--")
                else short_specs[raw_flag[1:]])
        opts[spec.storage_key] = raw_value if spec.takes_value else ""
    return opts, positionals, []


def _collect_unknown_tokens(
        argv: List[str],
        long_specs: Dict[str, OptSpec],
        short_specs: Dict[str, OptSpec],
) -> List[str]:
    """Walk `argv` once and return the user-typed tokens of every unknown flag, paired with their adjacent value when one was supplied.

    The output is meant to be re-emitted verbatim in the error message,
    so we preserve the user's syntax (e.g. `--foo=bar` stays a single token while `--foo bar` stays two).
    """
    unknown: List[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            name = a[2:].split("=", 1)[0]
            if name in long_specs:
                spec = long_specs[name]
                if spec.takes_value and "=" not in a and i + 1 < len(argv):
                    i += 1  # consume the value
            else:
                unknown.append(a)
                # If `--foo bar` (no `=`) and `bar` is unlikely to be its own flag,
                # also include it for display so the user sees the full unrecognized pair.
                if "=" not in a and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                    i += 1
                    unknown.append(argv[i])
            i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            short = a[1:]
            # Match `-X`, `-Xvalue` (when -X takes a value) but treat anything else (e.g. `-gs`, `-q`) as unknown.
            if short[0] in short_specs and (
                    len(short) == 1 or short_specs[short[0]].takes_value):
                spec = short_specs[short[0]]
                if spec.takes_value and len(short) == 1 and i + 1 < len(argv):
                    i += 1
            else:
                unknown.append(a)
            i += 1
            continue
        i += 1
    return unknown


# ────────────────────────────────────────────────────────────────────────────
# Validation + error formatting
# ────────────────────────────────────────────────────────────────────────────


def _close_matches(value: str, candidates: Iterable[str]) -> List[str]:
    return difflib.get_close_matches(
        value, list(candidates), n=_MAX_SUGGESTIONS, cutoff=_CLOSE_MATCH_CUTOFF)


def _format_suggestions(suggestions: List[str], *, capitalize: bool = True) -> str:
    quoted = ", ".join(f"`{s}`" for s in suggestions)
    lead = "Did" if capitalize else "did"
    return f"{lead} you mean: {quoted}?"


def _format_choices(choices: Iterable[str]) -> str:
    return ", ".join(str(c) for c in choices)


def _visible_choices(positional: PositionalSpec) -> Tuple[str, ...]:
    # Callers (`_fail_invalid_choice`, `_fail_missing_required`) only reach this helper for positionals that already carry `choices=`,
    # so the empty-choices fallback is just a safety net.
    if not positional.choices:  # pragma: no cover
        return ()
    return tuple(c for c in positional.choices if c not in positional.hidden_choices)


def _apply_color_setting(color: Optional[str]) -> None:
    """Honor `--color` for stdout / stderr ANSI emission.

    Called from inside `parse_cmdline` (rather than waiting until the caller invokes `set_utils_global_variables`)
    so that any `MacheteException` raised from the validation phase below
    picks up the same flag values that the rest of the program will use.
    The exception's `.msg` is rendered once at `__init__` time, so the globals must be correct BEFORE the raise.
    """
    use_in_stdout = color == "always" or (color in {None, "auto"} and terminal.is_stdout_a_tty())
    use_in_stderr = color == "always" or (color in {None, "auto"} and terminal.is_stderr_a_tty())
    markup.use_ansi_escapes_in_stdout = use_in_stdout
    markup.use_ansi_escapes_in_stderr = use_in_stderr


def _argument_error(message: str) -> NoReturn:
    sys.stderr.write(message + "\n")
    sys.exit(ExitCode.ARGUMENT_ERROR)


def _fail_invalid_command(typed: str) -> NoReturn:
    lines = [f"Invalid command: {typed!r}"]
    # Build the user-visible vocabulary from canonical names + aliases.
    visible = [n for n, spec in COMMAND_BY_NAME_OR_ALIAS.items()
               if n == spec.name or n in spec.aliases]
    suggestions = _close_matches(typed, visible)
    if suggestions:
        lines.append(_format_suggestions(suggestions))
    else:
        # With ~30 commands the full listing would dwarf the error, so steer the user to `help` instead.
        lines.append("Run `git machete help` to see all available commands.")
    _argument_error("\n".join(lines))


def _fail_unrecognized(unknown_tokens: List[str], *, command: Optional[str]) -> NoReturn:
    message = "Unrecognized arguments: " + " ".join(unknown_tokens)

    # Build per-flag suggestions.
    # `--foo=bar` is split before fuzzy-matching so `--foo` (the actual misspelling) is what we compare against.
    flag_suggestions: List[Tuple[str, List[str]]] = []
    known_options = COMMON_OPTIONS + (
        COMMAND_BY_NAME_OR_ALIAS[command].options if command is not None else ()
    )
    known_flags = [f"--{o.long}" for o in known_options if o.long]
    for tok in unknown_tokens:
        if not tok.startswith("-"):
            continue
        flag = tok.split("=", 1)[0]
        close = _close_matches(flag, known_flags)
        if close:
            flag_suggestions.append((flag, close))

    if len(flag_suggestions) == 1:
        message += "\n" + _format_suggestions(flag_suggestions[0][1])
    elif flag_suggestions:
        lines = [
            f"For `{flag}`: {_format_suggestions(close, capitalize=False)}"
            for flag, close in flag_suggestions
        ]
        message += "\n" + "\n".join(lines)
    elif command is not None:
        message += f"\nSee `git machete help {command}` for usage."
    _argument_error(message)


def _validate_positionals(
        positionals: List[str],
        cmd: CommandSpec,
        positional_specs: Tuple[PositionalSpec, ...],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    remaining = list(positionals)

    for idx, pspec in enumerate(positional_specs):
        is_last = idx == len(positional_specs) - 1
        if pspec.multiple:
            # Consumes the rest of the positionals.
            values = remaining
            remaining = []
            if pspec.required and not values:  # pragma: no cover
                # No `multiple=True, required=True` positional currently exists in COMMANDS -
                # kept as a safety net so we'd notice immediately if a future command introduced one without also adding a test.
                _fail_missing_required(pspec)
            converted = [_convert_positional(pspec, v) for v in values]
            result[pspec.name] = converted
        else:
            if not remaining:
                if pspec.required:
                    _fail_missing_required(pspec)
                continue
            value = remaining.pop(0)
            if pspec.choices is not None and value not in pspec.choices:
                _fail_invalid_choice(pspec, value)
            result[pspec.name] = _convert_positional(pspec, value)
        if is_last and remaining:
            # Excess positionals are reported as unrecognized arguments.
            _fail_unrecognized(remaining, command=cmd.name)

    if remaining:
        # The command declares no positionals but the user passed some.
        _fail_unrecognized(remaining, command=cmd.name)

    return result


def _convert_positional(pspec: PositionalSpec, value: str) -> Any:
    if pspec.type_conv is None:
        return value
    try:
        return pspec.type_conv(value)
    except ValueError:
        type_name = getattr(pspec.type_conv, "__name__", "value")
        _argument_error(f"Argument {pspec.label}: invalid {type_name} value: {value!r}")


def _fail_invalid_choice(pspec: PositionalSpec, value: str) -> NoReturn:
    visible = _visible_choices(pspec)
    lines = [f"Invalid {pspec.label}: {value!r}"]
    suggestions = _close_matches(value, visible)
    if suggestions:
        lines.append(_format_suggestions(suggestions))
    else:
        lines.append(f"Possible values for {pspec.label} are: " + _format_choices(visible))
    _argument_error("\n".join(lines))


def _fail_missing_required(pspec: PositionalSpec) -> NoReturn:
    lines = [f"The following arguments are required: {pspec.label}"]
    if pspec.choices:
        lines.append(
            f"Possible values for {pspec.label} are: " +
            _format_choices(_visible_choices(pspec))
        )
    _argument_error("\n".join(lines))


def _validate_mutex_groups(
        opts: Dict[str, str],
        groups: Tuple[MutexGroup, ...],
        all_options: Tuple[OptSpec, ...],
) -> None:
    option_by_key = {o.storage_key: o for o in all_options}
    for group in groups:
        seen: List[str] = [key for key in group.options if key in opts]
        if len(seen) < 2:
            continue
        if group.message is not None:
            # Semantic rejection: propagated as MacheteException
            # so it surfaces via `assert_failure` and exits with MACHETE_EXCEPTION rather than ARGUMENT_ERROR.
            raise MacheteException(group.message)
        first = option_by_key[seen[0]].canonical_name
        second = option_by_key[seen[1]].canonical_name
        _argument_error(f"Argument {second}: not allowed with argument {first}")


def _validate_subcommand_restrictions(
        opts: Dict[str, str],
        parsed_positionals: Dict[str, Any],
        cmd: CommandSpec,
        selected: SubcommandSpec,
) -> None:
    """For every option/positional that's been parsed, verify the selected subcommand accepts it.

    Raise `MacheteException` with the `<thing> is only valid with <sub> subcommand(s).` wording if not.
    """

    # ---- options ----------------------------------------------------------
    selected_keys = {o.storage_key for o in selected.options}
    common_keys = {o.storage_key for o in cmd.options} | {o.storage_key for o in COMMON_OPTIONS}
    for key in opts:
        if key in selected_keys or key in common_keys:
            continue
        offering = [s.name for s in cmd.subcommands
                    if any(o.storage_key == key for o in s.options)]
        if not offering:
            # Should be unreachable: the parser only accepts options that belong to SOMETHING.
            continue  # pragma: no cover
        opt_spec = _find_option_by_key(cmd, key)
        flag_label = f"--{opt_spec.long}" if opt_spec and opt_spec.long else f"-{key}"
        raise MacheteException(
            f"`{flag_label}` option is only valid with "
            f"{_format_subcommand_list(offering)} {_subcommand_word(offering)}."
        )

    # ---- positionals ------------------------------------------------------
    for pspec in cmd.positionals:
        if pspec.only_with_subcommand is None:  # pragma: no cover
            # Every positional declared on a command-with-subcommands currently scopes itself to a subcommand
            # (github/gitlab's `request_id`); the unrestricted branch is kept defensively.
            continue
        value = parsed_positionals.get(pspec.name)
        # `multiple` positionals come back as lists; treat empty/None as "not supplied"
        # so we only fire when the user actually provided the positional under the wrong subcommand.
        if not value:
            continue
        if selected.name in pspec.only_with_subcommand:
            continue
        subs = list(pspec.only_with_subcommand)
        raise MacheteException(
            f"{pspec.label} is only valid with "
            f"{_format_subcommand_list(subs)} {_subcommand_word(subs)}."
        )


def _find_option_by_key(cmd: CommandSpec, key: str) -> Optional[OptSpec]:
    # Flatten cmd-level options and per-subcommand options into one stream so we don't need a separately-tested branch for each level -
    # in practice the only caller is the github/gitlab subcommand-restriction validator,
    # which only ever queries keys defined on a subcommand (cmd.options is empty for both code-hosting commands).
    candidates = itertools.chain(
        cmd.options,
        *(sub.options for sub in cmd.subcommands),
    )
    return next((o for o in candidates if o.storage_key == key), None)


def _format_subcommand_list(names: List[str]) -> str:
    quoted = [f"`{n}`" for n in names]
    if len(quoted) == 1:
        return quoted[0]
    if len(quoted) == 2:
        return f"{quoted[0]} and {quoted[1]}"
    return ", ".join(quoted[:-1]) + f" and {quoted[-1]}"


def _subcommand_word(names: List[str]) -> str:
    return "subcommand" if len(names) == 1 else "subcommands"
