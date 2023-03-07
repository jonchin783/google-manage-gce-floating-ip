#coding=utf-8
################################################################
### Console Multicloud Messaging Backend Microservice
### Written by Jonathan Chin, jonachin@cisco.com
### cisco Systems Singapore, 11 Feb 2020
################################################################
from __future__ import unicode_literals
from flask import Flask, jsonify, request, make_response
import requests, json
import os
import yaml

app = Flask(__name__)

def ccp_get_auth_token(ccp_ip, username, password):
    """ Function to perform ccp system login for token
    """
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    body = {'username': username, 'password': password}
    ccp_url = "https://" + ccp_ip + "/v3/system/login"
    response = requests.post(ccp_url, data=body, headers=headers, verify=False)
    return response.headers['X-Auth-Token']

def ccp_install_addon(ccp_ip, token, cluster_uuid, addon, addonName, addonDescription, addonURL):
    """ Function to perform addon deployment for tenant cluster
    """
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Auth-Token': token}
    body = {"name": addon, "displayName": addonName, "description": addonDescription, "url": addonURL}
    ccp_url = "https://" + ccp_ip + "/v3/clusters/" + cluster_uuid + "/addons/"
    response = requests.post(ccp_url, data=json.dumps(body), headers=headers, allow_redirects=True, verify=False)
    return response.content

def ccp_uninstall_addon(ccp_ip, token, cluster_uuid, addon):
    """ Function to perform addon deployment for tenant cluster
    """
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Auth-Token': token}
    ccp_url = "https://" + ccp_ip + "/v3/clusters/" + cluster_uuid + "/addons/"
    response = requests.delete(ccp_url, headers=headers, allow_redirects=True, verify=False)
    print(response)
    return response.content

def fetch_gcp_bearer_token():
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Metadata-Flavor': 'Google'}
    url = " http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    response = requests.get(url, headers=headers, verify=False)
    print (response)
    return response.content

def get_gce_instance():
    #headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    #ccp_url = "https://compute.googleapis.com/compute/v1/projects/jonchin-gps-argolis/zones/asia-southeast1-a/instances/jumphost-instance"
    #response = requests.get(ccp_url, headers=headers, allow_redirects=True, verify=False)
    #print(response)
    return fetch_gcp_bearer_token

def check_cluster_members():
    print("Opening cluster_conf...")
    file_directory = "/tmp/cluster_conf"
    inventory_file = os.path.join(file_directory, "cluster_conf.yaml")
    with open(inventory_file) as file:
        try:
            data = yaml.safe_load(file)
            #global gce_instances = {}
            for key, value in data.items():
                print(key, ":", value)
                if key == 'cluster':
                    gce_instances = value
        except yaml.YAMLError as exception:
            print(exception)
    return gce_instances

def check_cluster_vip():
    print("Opening cluster_conf...")
    file_directory = "/tmp/cluster_conf"
    inventory_file = os.path.join(file_directory, "cluster_conf.yaml")
    with open(inventory_file) as file:
        try:
            data = yaml.safe_load(file)
            #cluster_vip = {}
            for key, value in data.items():
                print(key, ":", value)
                if key == 'vip':
                    cluster_vip = value
        except yaml.YAMLError as exception:
            print(exception)
    return cluster_vip

def main():
    print("Opening cluster_conf...")
    file_directory = "./"
    inventory_file = os.path.join(file_directory, "cluster_conf.yaml")
    with open(inventory_file) as file:
        try:
            data = yaml.safe_load(file)
            # cluster_vip = {}
            print(data['gcp_project'])
            print(data['vip'])
            for key, value in data.items():
                if key == 'cluster':
                    gce_instances = value
                    print(value)
        except yaml.YAMLError as exception:
            print(exception)
    for x in gce_instances:
        if (x["instance"] == "cisco-jumphost"):
            print(x["location"])
    app.run(host='0.0.0.0', debug=True)

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

@app.route('/manage-gce-floating-ip/api/v1.0/get-cluster-members', methods=['GET'])
def get_cluster_members():
    return jsonify(check_cluster_members()), 200

@app.route('/manage-gce-floating-ip/api/v1.0/get-cluster-vip', methods=['GET'])
def get_cluster_vip():
    return jsonify(check_cluster_vip()), 200

@app.route('/manage-gce-floating-ip/api/v1.0/get-all-instances', methods=['GET'])
def get_all_instances():
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Metadata-Flavor': 'Google'}
    token_url = " http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    token_response = requests.get(token_url, headers=headers, verify=False)
    # check response is 200/201, then make calls to get the instance
    output = json.loads(token_response.content)
    print(output)
    api_key = output["access_token"]
    print(api_key)
    api_header = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': 'Bearer ' + api_key}
    for x in gce_instances:
        instance_url = "https://compute.googleapis.com/compute/v1/projects/" + gcp_project + "/zones/asia-southeast1-a/instances"
        instance_response = requests.get(instance_url, headers=api_header, verify=False)
        print(instance_response)
    return "OK", 201

@app.route('/manage-gce-floating-ip/api/v1.0/get-api-key', methods=['POST'])
def get_api_key():
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Metadata-Flavor': 'Google'}
    url = " http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    response = requests.get(url, headers=headers, verify=False)
    # check response is 200/201, then make calls to get the instance
    print(response)
    return response.content['access_token'], 201

@app.route('/manage-gce-floating-ip/api/v1.0/get-instance', methods=['POST'])
def get_instance():
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Metadata-Flavor': 'Google'}
    url = " http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    response = requests.get(url, headers=headers, verify=False)
    # check response is 200/201, then make calls to get the instance
    print(response)
    return response.content, 201

@app.route('/multicloud-backend/api/v1.0/ccp-login', methods=['POST'])
def ccp_login():
    response = ccp_get_auth_token(request.json['ccp-ip'], request.json['username'], request.json['password'])
    return jsonify({'auth_token': response}), 201

@app.route('/multicloud-backend/api/v1.0/ccp-deploy-addon', methods=['POST'])
def ccp_deploy_addon():
    token_response = ccp_get_auth_token(request.json['ccp-ip'], request.json['username'], request.json['password'])
    response = ccp_install_addon(request.json['ccp-ip'], token_response, request.json['cluster-uuid'], request.json['name'], request.json['displayName'], request.json['description'], request.json['url'])
    return response, 200

@app.route('/multicloud-backend/api/v1.0/ccp-undeploy-addon', methods=['POST'])
def ccp_undeploy_addon():
    token_response = ccp_get_auth_token(request.json['ccp-ip'], request.json['username'], request.json['password'])
    response = ccp_uninstall_addon(request.json['ccp-ip'], token_response, request.json['cluster-uuid'], request.json['name'])
    return response, 200

if __name__ == '__main__':
    main()

