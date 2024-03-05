Setting this config key to ``true`` will force ``git machete gitlab create-mr`` to take MR description
from the message body of the first unique commit of the branch, even if ``.git/info/description`` and/or ``.gitlab/merge_request_templates/Default.md`` is present.
