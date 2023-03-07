#coding=utf-8
##################################################################################
### Python Microservices to manage floating IP for MySQL servers on GCE instances
### Jonathan Chin, jonchin@google.com
### Google Asia Pacific, Singapore, 6 Mar 2023
##################################################################################
from __future__ import unicode_literals
from flask import Flask, jsonify, request, make_response
import requests, json
import os, sys, logging
import yaml

app = Flask(__name__)
gcp_project = ""
cluster_vip = ""
gce_instances = {}

def get_conf_inventory():
    print("INFO - get_conf_inventory : reading cluster config file...")
    file_directory = "/tmp/cluster_conf"
    inventory_file = os.path.join(file_directory, "cluster_conf.yaml")
    with open(inventory_file) as file:
        try:
            data = yaml.safe_load(file)
            global gcp_project, cluster_vip, gce_instances
            gcp_project = data['gcp_project']
            cluster_vip = data['vip']
            for key, value in data.items():
                if key == 'cluster':
                    gce_instances = value
        except yaml.YAMLError as exception:
            print(exception)

def get_instance_zone(instance_name):
    app.logger.info("INFO - get_instance_zone : checking the GCP zone of instance " + instance_name)
    output = json.dumps(gce_instances)
    instance_list = json.loads(output)
    for x in instance_list:
        if (x['instance'] == instance_name):
            app.logger.info(x['location'])
            return x['location']

def fetch_bearer_token():
    print("INFO - fetch_bearer_token : getting Google API bearer token key...")
    headers = {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json',
               'Metadata-Flavor': 'Google'}
    url = " http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    response = requests.get(url, headers=headers, verify=False)
    resp = json.loads(response.content)
    return resp['access_token']

def main():
    get_conf_inventory()
    app.run(host='0.0.0.0', debug=True)

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

@app.route('/manage-gce-floating-ip/api/v1.0/get-cluster-members', methods=['GET'])
def get_cluster_members():
    return str(gce_instances), 200

@app.route('/manage-gce-floating-ip/api/v1.0/get-cluster-vip', methods=['GET'])
def get_cluster_vip():
    return str(cluster_vip), 200

@app.route('/manage-gce-floating-ip/api/v1.0/get-api-key', methods=['POST'])
def get_api_key():
    headers = \
        {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json', 'Metadata-Flavor': 'Google'}
    url = " http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    response = requests.get(url, headers=headers, verify=False)
    resp = json.loads(response.content)
    return resp['access_token'], 200

@app.route('/manage-gce-floating-ip/api/v1.0/get-master-instance', methods=['GET'])
def get_master_instance():
    print("INFO - get_master_instance: checking the current master instance with vip" + cluster_vip)
    vip_address = cluster_vip + "/32"
    api_key = fetch_bearer_token()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                  'Authorization': 'Bearer ' + api_key}
    output = json.dumps(gce_instances)
    instance_list = json.loads(output)
    for x in instance_list:
        url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + x['location'] + \
              "/instances/" + x['instance']
        response = requests.get(url, headers=headers, verify=True)
        instance_output = json.loads(response.content)
        if "aliasIpRanges" in instance_output['networkInterfaces'][0]:
            app.logger.info(instance_output['networkInterfaces'][0]['aliasIpRanges'][0]['ipCidrRange'])
            if (instance_output['networkInterfaces'][0]['aliasIpRanges'][0]['ipCidrRange'] == vip_address):
                app.logger.info("Master Instance is " + x['instance'])
                return "Master Instance is " + x['instance'], 200

    return "Master Instance not found", 404

@app.route('/manage-gce-floating-ip/api/v1.0/get-instance/<instance_name>', methods=['GET'])
def get_instance(instance_name):
    print("INFO - get_instance: fetching information of instance " + instance_name)
    zone = get_instance_zone(instance_name)
    api_key = fetch_bearer_token()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                  'Authorization': 'Bearer ' + api_key}
    url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + zone + \
          "/instances/" + instance_name
    response = requests.get(url, headers=headers, verify=True)
    return response.content, 200

@app.route('/manage-gce-floating-ip/api/v1.0/demote-master/<instance_name>', methods=['POST'])
def demote_master(instance_name):
    app.logger.info("INFO - demote-master: demoting instance" + instance_name)
    api_key = fetch_bearer_token()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
               'Authorization': 'Bearer ' + api_key}
    output = json.dumps(gce_instances)
    instance_list = json.loads(output)
    for x in instance_list:
        if (x['instance'] == instance_name):
            url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + \
                  x['location'] + "/instances/" + x['instance']
            response = requests.get(url, headers=headers, verify=True)
            instance_output = json.loads(response.content)
            nic_fingerprint = instance_output['networkInterfaces'][0]['fingerprint']
            patch_url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + x[
                'location'] + "/instances/" + x['instance'] + "/updateNetworkInterface?alt=json&networkInterface=nic0"
            body = {"fingerprint": nic_fingerprint, "aliasIpRanges": []}
            response = requests.patch(patch_url, headers=headers, data=json.dumps(body), verify=True)
            app.logger.info(response.content)
            return "Instance " + instance_name + " demoted", 200

    return "Instance " + instance_name + " not found!", 404

@app.route('/manage-gce-floating-ip/api/v1.0/promote-master/<instance_name>', methods=['POST'])
def promote_master(instance_name):
    app.logger.info("INFO - promote-master: promoting instance" + instance_name + " as the new master")
    api_key = fetch_bearer_token()
    output = json.dumps(gce_instances)
    instance_list = json.loads(output)
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
               'Authorization': 'Bearer ' + api_key}
    app.logger.info("INFO - promote-master: first, look for the current master instance with vip" + cluster_vip)
    vip_address = cluster_vip + "/32"

    for x in instance_list:
        poll_url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + \
              x['location'] + "/instances/" + x['instance']
        response = requests.get(poll_url, headers=headers, verify=True)
        instance_output = json.loads(response.content)
        nic_fingerprint = instance_output['networkInterfaces'][0]['fingerprint']
        if "aliasIpRanges" in instance_output['networkInterfaces'][0]:
            app.logger.info(instance_output['networkInterfaces'][0]['aliasIpRanges'][0]['ipCidrRange'])
            if (instance_output['networkInterfaces'][0]['aliasIpRanges'][0]['ipCidrRange'] == vip_address):
                app.logger.info("INFO - promote-master: Current Master Instance is " + x['instance'])
                if (x['instance'] == instance_name):
                    return "Master Instance is already " + instance_name, 409
                else:
                    app.logger.info("INFO - promote-master: Cleaning up the master " + x['instance'])
                    patch_url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + \
                                x['location'] + "/instances/" + x['instance'] + \
                                "/updateNetworkInterface?alt=json&networkInterface=nic0"
                    body = {"fingerprint": nic_fingerprint, "aliasIpRanges": []}
                    response = requests.patch(patch_url, headers=headers, data=json.dumps(body), verify=True)
                    app.logger.info(response.content)
        else:
            app.logger.info("INFO - promote-master: Cleaning up the slaves " + x['instance'])
            patch_url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + \
                        x['location'] + "/instances/" + x['instance'] + \
                        "/updateNetworkInterface?alt=json&networkInterface=nic0"
            body = {"fingerprint": nic_fingerprint, "aliasIpRanges": []}
            response = requests.patch(patch_url, headers=headers, data=json.dumps(body), verify=True)
            app.logger.info(response.status_code)

    for y in instance_list:
        if (y['instance'] == instance_name):
            for z in range(0, 3):
                app.logger.info("INFO = promote-master: Attempt # " + str(z))
                app.logger.info("INFO - promote-master: Working on the new master " + y['instance'])
                check_url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + \
                      y['location'] + "/instances/" + y['instance']
                response = requests.get(check_url, headers=headers, verify=True)
                instance_output = json.loads(response.content)
                nic_fingerprint = instance_output['networkInterfaces'][0]['fingerprint']
                app.logger.info(response.status_code)
                patch_url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/" + y[
                    'location'] + "/instances/" + y['instance'] + \
                            "/updateNetworkInterface?alt=json&networkInterface=nic0"
                body = {"aliasIpRanges": [{"ipCidrRange": vip_address}], "fingerprint": nic_fingerprint}
                response = requests.patch(patch_url, headers=headers, data=json.dumps(body), verify=True)
                app.logger.info(response.status_code)

                response = requests.get(check_url, headers=headers, verify=True)
                instance_output = json.loads(response.content)
                app.logger.info("INFO - promote-master: Checking if the new master instance " + y['instance'] + \
                                " has the vip...")
                if "aliasIpRanges" in instance_output['networkInterfaces'][0]:
                    app.logger.info("INFO = promote-master: new Master instance " + y['instance'] + \
                                    " has the VIP address " + \
                                    instance_output['networkInterfaces'][0]['aliasIpRanges'][0]['ipCidrRange'])
                    if (instance_output['networkInterfaces'][0]['aliasIpRanges'][0]['ipCidrRange'] == vip_address):
                        return "Instance " + instance_name + " successfully promoted to new master", 200

    return "Instance " + instance_name + " failed to promote to new master", 404

if __name__ == '__main__':
    print("hello")
    get_conf_inventory()
    app.run(host='0.0.0.0', debug=True)

