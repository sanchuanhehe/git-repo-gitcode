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

import sys

import requests

from command import Command
from git_config import GitConfig
from settings import GITCODE_PR_V5_API
from settings import TIMEOUT


class GitcodePr(Command):
    COMMON = True
    helpSummary = "Show the open GitCode pull request for a pushed branch"
    helpUsage = """
%prog --br=<branch> [<project>...]
"""
    helpDescription = """
'%prog' looks up the open pull request that was opened from the given
branch (--br) for each project and prints its web url.
"""

    def _Options(self, p):
        p.add_option(
            "--br",
            type="string",
            action="store",
            dest="branch",
            help="branch that has been pushed",
        )

    def Execute(self, opt, args):
        result = []
        if opt.branch:
            branch = opt.branch
        else:
            print("error: need --br option", file=sys.stderr)
            sys.exit(1)

        for project in self.GetProjects(args):
            if project.revisionExpr:
                base_branch = project.revisionExpr
            else:
                base_branch = project.manifest.default.revisionExpr
            project_name = project.name
            branch_tmp = project.GetBranch(branch)
            if not branch_tmp.LocalMerge:
                continue
            branch_name = branch

            name_space = project._GitcodeNamespace()
            token = self.manifest.manifestProject.config.GetString("repo.token")
            if not token:
                token = GitConfig.ForUser().GetString("repo.token")
                if not token:
                    sys.stderr.write(
                        "repo.token is None, Please set it, you need "
                        "`repo config -h`\n"
                    )
                    sys.exit(1)
            p_list = {
                "project_name": project_name,
                "base": base_branch,
                "head": branch_name,
            }
            url = "/".join(
                [GITCODE_PR_V5_API, name_space, project_name, "pulls"]
            )
            payload = {
                "base": base_branch,
                "head": branch_name,
                "access_token": token,
                "state": "open",
            }
            try:
                r = requests.get(url, params=payload, timeout=TIMEOUT)
                pr_url = [tmp["html_url"] for tmp in r.json()]
                if pr_url:
                    p_list["pull_request"] = pr_url
                else:
                    continue
                result.append(p_list)
            except Exception as e:
                sys.stderr.write("ERROR: %s\n" % e)
                sys.exit(1)

        for project in result:
            print(
                "%s %-15s pr_url: %s"
                % (
                    project["project_name"],
                    project["head"],
                    project["pull_request"][0],
                )
            )
