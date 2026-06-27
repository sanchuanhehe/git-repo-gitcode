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

import re
import sys
import time

from color import Coloring
from command import InteractiveCommand
from editor import Editor
from error import ForkProjectError
from error import GitError
from error import PullRequestError
from error import UploadError


def _die(fmt, *args):
    msg = fmt % args
    print("error: %s" % msg, file=sys.stderr)
    sys.exit(1)


def _SplitUsers(values):
    result = []
    for value in values:
        result.extend([s.strip() for s in value.split(",")])
    return result


class PushColoring(Coloring):
    def __init__(self, config):
        super().__init__(config, "status")
        self.fork = self.printer("fork", fg="green")


class Push(InteractiveCommand):
    COMMON = True
    helpSummary = "Push changes and open pull requests on GitCode"
    helpUsage = """
%prog [--br=<branch>] [--d=<dest>] [-p] [<project>...]
"""
    helpDescription = """
The '%prog' command pushes local topic branches to the GitCode server and,
unless disabled, opens a pull request against the destination branch.

It searches for pushable branches in all projects listed at the command
line.  Projects can be specified either by name, or by a relative or
absolute path to the project's local directory.  If no projects are
specified, '%prog' searches every project in the manifest.

If the project is not yet forked under your account and the push is
rejected, '%prog' automatically forks it on GitCode; run '%prog' again
once the fork has finished syncing to complete the push and PR.

Configuration
-------------

repo.token:

A GitCode personal access token, used to authenticate API calls (fork,
pull request, user lookup).  Set it with `repo config repo.token <TOKEN>`.

repo.pullrequest:

If set to "False", '%prog' only pushes and does not open a pull request.
The -p/--pr_force flag forces a pull request even when this is "False".
"""

    def _Options(self, p):
        p.add_option(
            "--new_branch",
            dest="new_branch",
            action="store_true",
            help="create a new feature branch on the git server",
        )
        p.add_option(
            "-p",
            "--pr_force",
            dest="pr_force",
            action="store_true",
            help="create a pull request even when repo.pullrequest is False",
        )
        p.add_option(
            "--title",
            type="string",
            action="store",
            dest="title",
            help="title of the pull request",
        )
        p.add_option(
            "--content",
            type="string",
            action="store",
            dest="content",
            help="body of the pull request",
        )
        p.add_option(
            "-f",
            "--force",
            dest="force",
            action="store_true",
            help="push without rewind check",
        )
        p.add_option(
            "--d",
            "--dest_branch",
            type="string",
            action="store",
            dest="dest_branch",
            help="destination branch of the pull request",
        )
        p.add_option(
            "--re",
            "--reviewers",
            type="string",
            action="append",
            dest="reviewers",
            help="request reviews from these people",
        )
        p.add_option(
            "--br",
            type="string",
            action="store",
            dest="branch",
            help="branch to push",
        )

    def _SingleBranch(self, opt, branch, peoples):
        project = branch.project
        name = branch.name
        remote = project.GetBranch(name).remote

        key = "review.%s.autoupload" % remote.review
        answer = project.config.GetBoolean(key)

        if answer is False:
            _die("upload blocked by %s = false" % key)

        if answer is None:
            date = branch.date
            commit_list = branch.commits

            print("Upload project %s/:" % project.relpath)
            print(
                "  branch %s (%2d commit%s, %s):"
                % (
                    name,
                    len(commit_list),
                    len(commit_list) != 1 and "s" or "",
                    date,
                )
            )
            for commit in commit_list:
                print("         %s" % commit)

            pushurl = project.manifest.manifestProject.config.GetString(
                "repo.pushurl"
            )
            sys.stdout.write(
                "to %s (y/n)? " % (pushurl and "server: " + pushurl or "remote")
            )
            sys.stdout.flush()
            answer = sys.stdin.readline().strip()
            answer = answer in ("y", "Y", "yes", "1", "true", "t")

        if answer:
            self._UploadAndReport(opt, [branch], peoples)
        else:
            _die("upload aborted by user")

    def _MultipleBranches(self, opt, pending, peoples):
        projects = {}
        branches = {}

        script = []
        script.append("# Uncomment the branches to push:")
        for project, avail in pending:
            script.append("#")
            script.append("# project %s/:" % project.relpath)

            b = {}
            for branch in avail:
                name = branch.name
                date = branch.date
                commit_list = branch.commits

                if b:
                    script.append("#")
                script.append(
                    "#  branch %s (%2d commit%s, %s):"
                    % (
                        name,
                        len(commit_list),
                        len(commit_list) != 1 and "s" or "",
                        date,
                    )
                )
                for commit in commit_list:
                    script.append("#         %s" % commit)
                b[name] = branch

            projects[project.relpath] = project
            branches[project.name] = b
        script.append("")

        script = Editor.EditString("\n".join(script)).split("\n")

        project_re = re.compile(r"^#?\s*project\s*([^\s]+)/:$")
        branch_re = re.compile(r"^\s*branch\s*([^\s(]+)\s*\(.*")

        project = None
        todo = []

        for line in script:
            m = project_re.match(line)
            if m:
                name = m.group(1)
                project = projects.get(name)
                if not project:
                    _die("project %s not available for upload", name)
                continue

            m = branch_re.match(line)
            if m:
                name = m.group(1)
                if not project:
                    _die("project for branch %s not in script", name)
                branch = branches[project.name].get(name)
                if not branch:
                    _die("branch %s not in %s", name, project.relpath)
                todo.append(branch)
        if not todo:
            _die("nothing uncommented for upload")

        self._UploadAndReport(opt, todo, peoples)

    def _UploadAndReport(self, opt, todo, peoples):
        out = PushColoring(self.manifest.manifestProject.config)
        out.redirect(sys.stderr)
        exist_regex = r"^ 已存在相同源分支.*"
        have_errors = False
        for branch in todo:
            branch.have_pr_errors = False
            branch.have_pr = False
            try:
                # Check for local changes that may have been forgotten.
                if branch.project.HasChanges():
                    key = "review.%s.autoupload" % branch.project.remote.review
                    answer = branch.project.config.GetBoolean(key)

                    # Don't ask when auto upload is configured.
                    if answer is None:
                        sys.stdout.write(
                            "Uncommitted changes in "
                            + branch.project.name
                            + " (did you forget to amend?). Continue "
                            "uploading? (y/n) "
                        )
                        a = sys.stdin.readline().strip().lower()
                        if a not in ("y", "yes", "t", "true", "on"):
                            print("skipping upload", file=sys.stderr)
                            branch.uploaded = False
                            branch.error = "User aborted"
                            continue
                branch.project.UploadNoReview(opt, peoples, branch=branch.name)
                branch.uploaded = True
                pull_request = self.manifest.manifestProject.config.GetString(
                    "repo.pullrequest"
                )
                if (
                    not (pull_request and pull_request == "False")
                    or opt.pr_force
                ):
                    branch.have_pr = True
                    branch.pull_requested = True
                    times = 3
                    while True:
                        try:
                            branch.pr_url = branch.project.PullRequest(
                                opt, branch.name, peoples
                            )
                            break
                        except PullRequestError as e:
                            if times and re.search("源分支.*不存在", str(e)):
                                times -= 1
                                print(
                                    "Created PR failed due to push hook may "
                                    "still execute. Retry after 2 seconds",
                                    file=sys.stderr,
                                )
                                time.sleep(2)
                                continue
                            else:
                                raise e
            except UploadError as e:
                branch.error = e
                branch.uploaded = False
                have_errors = True
            except GitError as e:
                print("Error: " + str(e), file=sys.stderr)
                sys.exit(1)
            except PullRequestError as e:
                branch.pr_error = e
                branch.pull_requested = False
                have_errors = True
                branch.have_pr_errors = True

        print(file=sys.stderr)
        print(
            "-" * 70,
            file=sys.stderr,
        )

        if have_errors:
            for branch in todo:
                if not branch.uploaded:
                    if len(str(branch.error)) <= 30:
                        fmt = " (%s)"
                    else:
                        fmt = "\n       (%s)"
                    print(
                        ("[PUSH  FAILED] %-15s %-15s" + fmt)
                        % (
                            branch.project.relpath + "/",
                            branch.name,
                            str(branch.error),
                        ),
                        file=sys.stderr,
                    )
                    # The project may not be forked yet; try to fork it.
                    try:
                        status_code, msg = branch.project.ForkProject()
                        if status_code == 200:
                            fork_info = (
                                "Remote repository is syncing code, please "
                                "wait for a while"
                            )
                            out.fork(
                                "[FORK      OK] %-15s %-15s (%s) \n"
                                % (
                                    branch.project.relpath + "/",
                                    branch.name,
                                    fork_info,
                                )
                            )
                        else:
                            print(
                                "[FORK  FAILED] %-15s %-15s (%s)"
                                % (
                                    branch.project.relpath + "/",
                                    branch.name,
                                    str(msg["error_message"]),
                                ),
                                file=sys.stderr,
                            )
                    except ForkProjectError as e:
                        print(
                            "[FORK  FAILED] %-15s %-15s (%s)"
                            % (
                                branch.project.relpath + "/",
                                branch.name,
                                str(e),
                            ),
                            file=sys.stderr,
                        )

                if branch.have_pr_errors:
                    if not branch.pull_requested:
                        check_error = str(branch.pr_error).split(":")
                        if len(check_error) >= 4 and re.match(
                            exist_regex, check_error[3]
                        ):
                            continue
                        if len(str(branch.pr_error)) <= 30:
                            fmt = " (%s)"
                        else:
                            fmt = "\n       (%s)"
                        print(
                            ("[PR    FAILED] %-15s %-15s" + fmt)
                            % (
                                branch.project.relpath + "/",
                                branch.name,
                                str(branch.pr_error),
                            ),
                            file=sys.stderr,
                        )

            print(
                "'if your PR FAILED or FORK OK, `repo push` again to create "
                "PR after handling the thing'",
                file=sys.stderr,
            )
            print()

        for branch in todo:
            if branch.uploaded:
                print(
                    "[PUSH      OK] %-15s %s "
                    % (branch.project.relpath + "/", branch.name),
                    file=sys.stderr,
                )
            if branch.have_pr:
                if branch.pull_requested:
                    print(
                        "[PR        OK] %-15s %s pr_url: %s"
                        % (
                            branch.project.relpath + "/",
                            branch.name,
                            branch.pr_url,
                        ),
                        file=sys.stderr,
                    )

        if have_errors:
            sys.exit(1)

    def Execute(self, opt, args):
        opt.new_branch = True
        project_list = self.GetProjects(args)
        pending = []
        reviewers = []
        branch = None
        if opt.branch:
            branch = opt.branch
        # force push only allows one project
        if opt.force:
            if len(project_list) != 1:
                print(
                    "error: --force requires exactly one project",
                    file=sys.stderr,
                )
                sys.exit(1)

        # If not creating a new branch, only push branches with new commits.
        for project in project_list:
            branch_tmp = branch if branch else project.CurrentBranch
            if (
                not opt.new_branch
                and project.GetUploadableBranch(branch_tmp) is None
            ):
                continue
            rb = project.GetPushableBranch(branch_tmp)
            if rb:
                pending.append((project, [rb]))

        if opt.reviewers:
            reviewers = _SplitUsers(opt.reviewers)

        if not pending:
            print("no branches ready for upload", file=sys.stderr)
        elif len(pending) == 1 and len(pending[0][1]) == 1:
            self._SingleBranch(opt, pending[0][1][0], reviewers)
        else:
            self._MultipleBranches(opt, pending, reviewers)
