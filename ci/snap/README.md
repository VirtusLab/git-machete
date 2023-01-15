Note that this directory is distinct from top-level [snap/](https://github.com/VirtusLab/git-machete/tree/master/snap) directory.

To regenerate Snapcraft token:

- Change the password to `admin@virtuslab.com` account at [login.ubuntu.com](https://login.ubuntu.com/) + update in password manager.
  See [Snapcraft forum thread](https://forum.snapcraft.io/t/is-there-any-way-to-expire-snapcraft-credentials/33483).

- Install [`snapcraft`](https://snapcraft.io/docs/installing-snapcraft).

- Generate a new token:
  ```shell
  snapcraft export-login ~/.snapcraft-credentials`
  ```
  Use `admin@virtuslab.com` account. Password to be found in password manager.

- Verify the token works:
  ```shell
  SNAPCRAFT_STORE_CREDENTIALS=$(<~/.snapcraft-credentials) snapcraft whoami
  ```

  You should see something like:
  ```
  email: admin@virtuslab.com
  username: virtuslab
  id: <...>
  permissions: package_access, package_manage, package_metrics, package_push, package_register, package_release, package_update
  channels: no restrictions
  expires: <ONE YEAR FROM NOW>
  ```

  As of snapcraft v7.2, regardless of `--expiry` option passed to `snapcraft export-login`,
  the tokens will have at most one-year expiry.
  There's a cyclic event in VirtusLab Google Calendar to remind of the expiry.
  I refrained from setting up CI cron as this would require keeping Ubuntu One credentials in the CI.

- Copy the credentials:
  ```shell
  pbcopy < ~/.snapcraft-credentials
  ```
  As of snapcraft v7.2, they'll be base64-encoded already, no need to re-base64-encode.

- Update the credentials in password manager.

- And crucially, update the credentials in CircleCI (`SNAPCRAFT_STORE_CREDENTIALS` env var).
