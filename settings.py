# Copyright (C) 2020 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""GitCode integration settings.

Endpoints and constants used by the GitCode-specific commands (``repo push``
and ``repo gitcode_pr``).
"""

TIMEOUT = 10
GITCODE_SSH = "git@gitcode.com"
GITCODE_USER_API = "https://api.gitcode.com/api/v3/user"
GITCODE_PR_V3_API = "https://api.gitcode.com/api/v3/projects"
GITCODE_PR_V5_API = "https://api.gitcode.com/api/v5/repos"
GITCODE_URL = "https://gitcode.com"
