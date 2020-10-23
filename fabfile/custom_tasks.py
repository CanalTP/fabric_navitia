# coding=utf-8

# Copyright (c) 2001-2015, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of fabric_navitia, the provisioning and deployment tool
#     of Navitia, the software to build cool stuff with public transport.
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
# IRC #navitia on freenode
# https://groups.google.com/d/forum/navitia
# www.navitia.io

"""
This file contains some specific tasks not to be run everytime
"""
import os
from datetime import datetime

from fabric.api import env, local
from fabric.colors import red
from fabric.context_managers import cd, warn_only
from fabric.contrib.files import exists
from fabric.decorators import task, roles
from fabric.operations import run, put, sudo
from fabric.tasks import execute

# WARNING: the way fabric_navitia imports are done as a strong influence
#          on the resulting naming of tasks, wich can break integration tests
import fabfile.component
from fabfile.utils import _upload_template, _random_generator, apt_get_update


@task
@roles('tyr_master')
def update_all_ed_databases_to_alembic():
    """
     Migrate ED database handled by bash scripts to alembic.

     Must be called only during the database migration to alembic (navitia 1.1.3 to 1.2.0)

     This function can be deleted after this migration
    """
    for i in env.instances.values():
        if exists("{env}/{instance}".format(env=env.ed_basedir, instance=i.name)):
            with cd("{env}/{instance}".format(env=env.ed_basedir, instance=i.name)):
                run("./update_db.sh settings.sh")
                run("PYTHONPATH=. alembic stamp 52b017632678")
                run("PYTHONPATH=. alembic upgrade head")
        else:
            print(red("ERROR: {env}/{instance} does not exists. skipping db update"
                      .format(env=env.ed_basedir, instance=i.name)))


@roles('tyr_master')
def cities_integration():
    """ Setup the cities module

    see https://github.com/CanalTP/puppet-navitia/pull/45 for more information
    """

    run("apt-get --yes install navitia-cities")
    run("pip install python-dateutil")

    # postgresql user + dedicated database
    postgresql_user = 'cities'
    postgresql_database = postgresql_user
    password = _random_generator()
    execute(component.db.create_postgresql_user, "cities", password)
    execute(component.db.create_postgresql_database, "cities")

    # init_db.sh
    execute(component.db.postgis_initdb, "cities")

    _upload_template("tyr/cities_alembic.ini.jinja",
                     "{}/cities_alembic.ini".format(env.tyr_basedir),
                     context={
                         'env': env,
                         'postgresql_database': postgresql_database,
                         'postgresql_user': postgresql_user,
                         'postgresql_password': password,
                     },
    )

    raw_input("Please add \"CITIES_DATABASE_URI = 'user={user} password={password} "
              "host={database_host} dbname={dbname}'\" in /srv/tyr/settings.py and press "
              "enter when finished.".format(password=password,
                                            database_host=env.ed_postgresql_database_host,
                                            dbname=postgresql_database,
                                            user=postgresql_user))

    with cd(env.tyr_basedir):
        run("alembic --config cities_alembic.ini upgrade head")
        if exists("/srv/ed/france-latest.osm.pbf"):
            run("TYR_CONFIG_FILE=/srv/tyr/settings.py ./manage.py {} "
                "/srv/ed/france-latest.osm.pbf".format(postgresql_database))
    execute(component.tyr.restart_tyr_worker)


@task
@roles('tyr_master')
def deploy_all_default_synonyms():
    """
    add default synonyms to all instances
    this should not be necesary after the migration as
    all new instances are deployed with the default synonyms
    """
    default_synonyms_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                         os.path.pardir, 'static_files', 'ed', 'default_synonyms.txt')
    for i in env.instances.values():
        put(default_synonyms_file, i.source_dir, use_sudo=True)
        sudo("chown {u} {f}".format(u=env.KRAKEN_USER, f=os.path.join(i.source_dir, 'default_synonyms.txt')))


@task
@roles('ws', 'tyr', 'eng')
def install_system_python_protobuf():
    """
    force uninstall python protobuf to allow using system protobuf
    """
    apt_get_update()
    sudo("apt-get --yes remove python-protobuf")
    sudo("apt-get --yes autoremove")
    with warn_only():
        sudo("pip uninstall --yes protobuf")
    sudo("! (pip freeze | grep -q protobuf)")
    sudo("apt-get --yes install python-protobuf")


@task
def get_packages(url):
    """
    retrieve debian package to install Navitia by source
    """
    mktemp = '/tmp/navitia_packages_{}'.format(datetime.now().strftime("%Y%m%d-%H%M%S"))

    env.debian_packages_path = mktemp

    local("mkdir {mktemp} && cd {mktemp} && wget --no-check-certificate {url}"
          .format(mktemp=mktemp, url=url))
    local("cd {} && unzip -j archive.zip".format(mktemp))
