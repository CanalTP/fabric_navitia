# Copyright (c) 2001-2014, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
#     the software to build cool stuff with public transport.
#
# Hope you'll enjoy and contribute to this project,
#     powered by Canal TP (www.canaltp.fr).
# Help us simplify mobility and open public transport:
#     a non ending quest to the responsive locomotion way of traveling!
#
# LICENCE: This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Stay tuned using
# twitter @navitia
# channel `#navitia` on riot https://riot.im/app/#/room/#navitia:matrix.org
# https://groups.google.com/d/forum/navitia
# www.navitia.io

# Title: Retreive Navitia Debian Packages from Github
#
# Github Actions is capable to create artifacts from a specific job.
# Artifacts can be downloaded via the github API
# We want to reteive the last Navitia Debian packages (in success) compressed in a zip file.
# To perform it, the script does:
# - Find the concerned workflow (id)
# - Retreive the last run (in success) of the workflow
# - Dowmload the associated artifacts (in a zip file)

import logging
import json
import requests
import wget
import sys
import os
import glob
import argparse
import zipfile

DEFAULT_WORKFLOW_NAME = "Build Navitia Packages For Dev Multi Distributions"
DEFAULT_OUTPUT_PATH = "."
DEFAULT_ARTIFACTS_NAME = "navitia-debian8-packages.zip"

class GithubArtifactsReceiver:
    def __init__(self, github_user, github_token, workflow_name=DEFAULT_WORKFLOW_NAME, artifacts_name=DEFAULT_ARTIFACTS_NAME, artifacts_output_path=DEFAULT_OUTPUT_PATH):
        self.github_user = github_user
        self.github_token = github_token
        self.workflow_name = workflow_name
        self.artifacts_output_path = artifacts_output_path
        self.artifacts_name = artifacts_name
        self.old_artifacts_to_remove = self.artifacts_output_path + "/" + self.artifacts_name
        self.url_header = "https://" + github_user + ":" + github_token + "@"
        self.workflows_url = self.url_header + "api.github.com/repos/CanalTP/navitia/actions/workflows"
        self.logger = logging.getLogger('github artifacts receiver')
        self._config_logger()
        self.logger.info("load artifacts receiver with github_user={}, github_token=TOKEN, workflow_name={}, artifacts_name={}, output_path={}".format(self.github_user, self.workflow_name, self.artifacts_name, self.artifacts_output_path))


    def retreive_workflow_id(self):
        """ Retreive workflow id from Build Navitia Package """
        resp = self.call(self.workflows_url)
        for workflow in resp["workflows"]:
            if workflow["name"] == self.workflow_name:
                self.logger.info("workflow id for {} is {}".format(self.workflow_name, workflow["id"]))
                return workflow["id"]
        self.logger.error("workflow name={}, does not exist".format(self.workflow_name))
        sys.exit("workflow does not exist")


    def retreive_artifacts_link_from_last_run(self, workflow_id):
        """ Retreive artifacts link from the last run """
        resp = self.call(self.workflows_url + "/" + str(workflow_id) + "/runs")
        last_workflow_run = max(resp["workflow_runs"], key=lambda w: w["run_number"])
        self.logger.info("last run workflow_id: {}".format(last_workflow_run["workflow_id"]))

        if last_workflow_run["conclusion"] != "success":
            self.logger.error("the last job, id {}, is not success".format(last_workflow_run["id"]))
            sys.exit("the last job is not success")

        if last_workflow_run["status"] != "completed":
            self.logger.error("the last job, id {}, is not completed".format(last_workflow_run["id"]))
            sys.exit("the last job is not completed")

        self.logger.info(
            "run id={} in success with artifacts url {}".format(last_workflow_run["id"], last_workflow_run["artifacts_url"]))
        return last_workflow_run["artifacts_url"], last_workflow_run["id"]

    def download_artifacts(self, artifacts_url, run_id):
        """ Download artifacts """
        artifacts_url = self.url_header + artifacts_url.replace('https://', '')
        resp = self.call(artifacts_url)
        if resp["total_count"] == 0:
            self.logger.error("No artifacts available for run {}".format(run_id))
            self.logger.error("Artifacts: https://api.github.com/repos/CanalTP/navitia/actions/runs/{}/artifacts".format(run_id))
            sys.exit()

        # the artifact that match
        zip_url = ""
        for artifact in resp["artifacts"]:
            if artifact["name"] == self.artifacts_name.split('.')[0]:
                artifact_info = artifact
                zip_url = self.url_header + artifact_info["archive_download_url"].replace('https://', '')
                self.logger.info("artifacts name - {}".format(artifact["name"]))
                break
        if zip_url == "":
            self.logger.error("no artifact available - run id {}".format(run_id))
            self.logger.error("Artifacts: https://api.github.com/repos/CanalTP/navitia/actions/runs/{}/artifacts".format(run_id))
            sys.exit()

        # Remove old artifacts with the same name if exist
        if os.path.isfile(self.old_artifacts_to_remove):
            self.logger.info("remove old artifacts - {}".format(self.old_artifacts_to_remove))
            os.remove(self.old_artifacts_to_remove)

        filename = ""
        self.logger.info("download {}".format(zip_url.split("@")[1]))
        filename = wget.download(zip_url, self.artifacts_output_path + "/" + self.artifacts_name)
        self.logger.info("File {} downloaded".format(filename))

        expected_file_size = artifact_info["size_in_bytes"]
        file_size = os.path.getsize(filename)
        delta_size = abs(expected_file_size - file_size)
        percent_diff_size = delta_size * 100. / file_size
        assert percent_diff_size < 0.1, "Downloaded file size ({} bytes) differs from expected size ({} bytes). \nDownload may have failed or disk may be full".format(file_size, expected_file_size)


    def _config_logger(self):
        self.logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)


    def call(self, url):
        self.logger.info("call {}".format(url.split("@")[1]))
        r = requests.get(url)
        return json.loads(r.text.encode('utf-8'))


    def check_github_api(self):
        self.logger.info("check github actions API")
        r = requests.get(self.workflows_url)
        if r.status_code == 200:
            self.logger.info("github API status 200")
        else:
            self.logger.error("github API status {}".format(r.status_code))
            self.logger.error("stop process")
            sys.exit("github API status != 200")


    def run(self):
        workflow_id = self.retreive_workflow_id()
        artifacts_url, run_id = self.retreive_artifacts_link_from_last_run(workflow_id)
        self.download_artifacts(artifacts_url, run_id)


def uncompress_artifacts(path_to_artifacts):
    """ uncompress the downloaded artifacts """
    zip = zipfile.ZipFile(path_to_artifacts)
    zip.extractall()
    zip.close()
    zip = zipfile.ZipFile(path_to_artifacts.replace('-', '_'))
    zip.extractall()
    zip.close()


def remove_all_artifacts(path_to_artifacts):
    """ remove old artifacts """
    for f in glob.glob("navitia-*"):
        os.remove(f)
    if os.path.isfile(path_to_artifacts):
        os.remove(path_to_artifacts)
    if os.path.isfile(path_to_artifacts.replace('-', '_')):
        os.remove(path_to_artifacts.replace('-', '_'))


def config_logger():
    logger = logging.getLogger('retreive debian package from github')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

def parse_args(parser, logger):
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", dest="github_user", help="Github user to call Github API (mandatory)")
    parser.add_argument("-t", dest="github_token", help="Github token to call Github API (mandatory)")
    parser.add_argument("-w", dest="workflow_name", help="Github Workflow name", default=DEFAULT_WORKFLOW_NAME)
    parser.add_argument("-a", dest="artifacts_name", help="Artifacts name", default=DEFAULT_ARTIFACTS_NAME)
    parser.add_argument("-o", dest="output_dir", help="Output path", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("-r", dest="remove_artifacts", help="Remove artifacts in current directory")
    parser.add_argument("-z", dest="uncompress_artifacts", help="Uncompress the downloaded artifacts")
    args = parser.parse_args()

    if not args.github_user and not args.remove_artifacts and not args.uncompress_artifacts:
        logger.error("Github user is a mandatory parameter")
        logger.error("Please fill -u parameter")
        sys.exit("Github user is a mandatory parameter")
    if not args.github_user and not args.remove_artifacts and not args.uncompress_artifacts:
        logger.error("Github token is a mandatory parameter")
        logger.error("Please fill -t parameter")
        sys.exit("Github token is a mandatory parameter")

    return args


def main():
    logger = config_logger()
    logger.info("start process")

    args = parse_args(argparse.ArgumentParser(), logger)

    if args.remove_artifacts:
        logger.info("remove old artifacts")
        remove_all_artifacts(args.remove_artifacts)
    elif args.uncompress_artifacts:
        logger.info("uncompress the downloaded artifacts")
        uncompress_artifacts(args.uncompress_artifacts)
        logger.info("you can have now acces to navitia-*.deb packages")
    else:
        artifacts_receiver = GithubArtifactsReceiver(args.github_user, args.github_token, args.workflow_name, args.artifacts_name, args.output_dir)
        artifacts_receiver.check_github_api()
        artifacts_receiver.run()

    logger.info("finish process")

if __name__ == "__main__":
    main()
