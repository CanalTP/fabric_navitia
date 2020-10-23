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

from fabric.colors import blue
from fabric.tasks import execute
from fabric.api import env, task
from fabfile.component import haproxy

def vip_name(instance):
    """ Return kraken vip name based on our convention """

    # ex.: UK-PRD-ENG, TEST-DEV-ENG
    return "{instance}-{env}-ENG" \
            .format(instance=instance.upper(),
                    env=env.name.upper().replace('PROD', 'PRD'))


@task
def remove_kraken_vip(name):
    """ Delete a given instance vip and associated pool """
    from fabfile.component import load_balancer

    pool_name = vip_name(name)
    vs_name = pool_name

    connection = load_balancer._adc_connection()

    print(blue("Delete virtual server %s" % vs_name))
    connection.LocalLB.VirtualServer.delete_virtual_server([vs_name])

    print(blue("Delete pool %s" % pool_name))
    connection.LocalLB.Pool.delete_pool([pool_name])


###################################################
#
#         LOAD BALANCERS MANAGEMENT TASKS
#
# First refactored in commit e725a2571b8bc.
# WARNING
# For the (dis)(en)abling of a kraken node to take
# effect, it is necessary to restart the jormun nodes
# that are enabled.
# So, some rules must be respected:
# 1- enable/disable kraken nodes first,
# 2- enable/disable jormun nodes, and if enabled,
#    restart it before (not mandatory).
# 3- last, restart any jormun that is enabled and
#    has not been restarted in step 2.
#
###################################################

@task
def disable_kraken_haproxy(krakens):
    for kraken in krakens:
        execute(haproxy.disable_kraken, kraken)

@task
def enable_kraken_haproxy(krakens):
    for kraken in krakens:
        execute(haproxy.enable_kraken, kraken)

@task
def disable_nodes(nodes):
    from fabfile.component import load_balancer
    for node in nodes:
        execute(load_balancer.disable_node, node)


@task
def enable_nodes(nodes):
    from fabfile.component import load_balancer
    for node in nodes:
        execute(load_balancer.enable_node, node)


@task
def restart_jormungandr(nodes, safe=True):
    from fabfile.component import jormungandr
    for node in nodes:
        execute(jormungandr.reload_jormun_safe, node, safe)


@task
def switch_to_first_phase(eng_hosts_1, ws_hosts_1, ws_hosts_2):
    #execute(disable_nodes, eng_hosts_1)
    execute(disable_kraken_haproxy, eng_hosts_1)
    execute(restart_jormungandr, ws_hosts_2)
    execute(disable_nodes, ws_hosts_1)


@task
def switch_to_second_phase(eng_hosts_1, eng_hosts_2, ws_hosts_1,  ws_hosts_2):
    # first, enable / disable kraken nodes
    #execute(enable_nodes, eng_hosts_1)
    execute(enable_kraken_haproxy, eng_hosts_1)
    #execute(disable_nodes, eng_hosts_2)
    execute(disable_kraken_haproxy, eng_hosts_2)
    # then enable / disable jormun nodes
    execute(enable_nodes, ws_hosts_1)
    execute(disable_nodes, ws_hosts_2)


@task
def switch_to_third_phase(ws_hosts_2):
    execute(enable_nodes, ws_hosts_2)


@task
def enable_all_nodes(eng_hosts, ws_hosts_1,  ws_hosts_2):
    execute(enable_kraken_haproxy, eng_hosts)
    execute(restart_jormungandr, ws_hosts_2)
    execute(restart_jormungandr, ws_hosts_1)
