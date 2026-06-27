# Copyright (C) 2010 The Android Open Source Project
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

from command import Command
from git_command import GitCommand


class Config(Command):
    COMMON = True
    helpSummary = "Get and set repo config"
    helpUsage = """
%prog name [value]
"""
    helpDescription = """
'%prog' gets or sets config of the manifest repository.

Only names beginning with 'repo.' may be set, e.g.:

  repo config repo.token <ACCESS_TOKEN>
  repo config repo.pullrequest True

Setting repo.token clears any cached repo.pushurl so the next push
re-resolves the fork namespace for the new account.
"""

    def _Options(self, p):
        p.add_option(
            "--bool",
            dest="bool",
            action="store_true",
            help='ensure that the output is "true" or "false"',
        )
        p.add_option(
            "--global",
            dest="Global",
            action="store_true",
            help="use the global git config file",
        )

    def Execute(self, opt, args):
        if not args:
            self.Usage()

        if len(args) > 1 and not args[0].startswith("repo."):
            print(
                "error: can only set config name starting with 'repo.', but "
                "you provided '%s'." % args[0],
                file=sys.stderr,
            )
            sys.exit(1)

        if len(args) > 1 and args[0] == "repo.mirror":
            print(
                "fatal: resetting repo.mirror is not supported on an "
                "existing client.",
                file=sys.stderr,
            )
            sys.exit(1)

        mp = self.manifest.manifestProject

        command = ["config"]
        if opt.bool:
            command.append("--bool")
        if opt.Global:
            command.append("--global")
        command.extend(args)

        if GitCommand(mp, command).Wait() != 0:
            return -1

        if len(args) > 1 and args[0] == "repo.token":
            # Token changed: drop the cached pushurl so it gets re-resolved.
            mp.config.SetString("repo.pushurl", None)
