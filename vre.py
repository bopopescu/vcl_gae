import os
import datetime
import time

# Google App Engine Python SDK includes Django 1.4 and 0.96, but 0.96 is 
# imported by default when import the django package.  The code below sets 
# configures the SDK to import Django version 1.4
# [https://developers.google.com/appengine/docs/python/tools/libraries27] 
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from google.appengine.dist import use_library
use_library('django', '1.3')

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import users

import boto
#import boto.manage.cmdshell # This does not work in GAE.
import boto.manage.server

# To prevent error:
# BotoClientError: BotoClientError: SSL server certificate validation is enabled in boto configuration, but Python dependencies required to support this feature are not available. Certificate validation is only supported when running under Python 2.6 or later.
if not boto.config.has_section('Boto'):
    boto.config.add_section('Boto')
boto.config.set('Boto', 'https_validate_certificates', 'False')

# Based on example at [https://gist.github.com/thurloat/425480].
config = boto.config
config.add_section('Credentials')
config.set('Credentials', 'aws_access_key_id', '')
config.set('Credentials', 'aws_secret_access_key', '')

# Virtual computer lab model
class computerlab(db.Model):
    labname = db.StringProperty()
    labdescription = db.StringProperty()
    coursename = db.StringProperty()
    coursecode = db.StringProperty()
    coursesemester = db.StringProperty()
    courseinstructor = db.StringProperty()
    amazonami = db.StringProperty()
    date_created = db.DateTimeProperty()
    lab_auth_info = db.StringProperty()
    lab_connection_options = db.StringProperty()    
    group_name = db.StringProperty()
    instance_type = db.StringProperty()

def create_instance(ami='ami-456ac22c',
                    instance_type='t1.micro',
                    key_name='',
                    key_extension='.pem',
                    key_dir='~/.ssh',
                    group_name='default',
                    ssh_port=22,
                    cidr='0.0.0.0/0',
                    tag='LBSC_670',
                    user_data=None,
                    cmd_shell=True,
                    login_user='ubuntu',
                    ssh_passwd=None,
                    username = '',
                    classcode='iSchool',
                    azone = 'us-east-1c'):
    """
    Launch an instance and wait for it to start running.
    Returns a tuple consisting of the Instance object and the CmdShell
    object, if request, or None.

    ami        The ID of the Amazon Machine Image that this instance will
               be based on.  Default is a 64-bit Amazon Linux EBS image.

    instance_type The type of the instance.

    key_name   The name of the SSH Key used for logging into the instance.
               It will be created if it does not exist.

    key_extension The file extension for SSH private key files.
    
    key_dir    The path to the directory containing SSH private keys.
               This is usually ~/.ssh.

    group_name The name of the security group used to control access
               to the instance.  It will be created if it does not exist.

    ssh_port   The port number you want to use for SSH access (default 22).

    cidr       The CIDR block used to limit access to your instance.

    tag        A name that will be used to tag the instance so we can
               easily find it later.

    user_data  Data that will be passed to the newly started
               instance at launch and will be accessible via
               the metadata service running at http://169.254.169.254.

    cmd_shell  If true, a boto CmdShell object will be created and returned.
               This allows programmatic SSH access to the new instance.

    login_user The user name used when SSH'ing into new instance.  The
               default is 'ec2-user'

    ssh_passwd The password for your SSH key if it is encrypted with a
               passphrase.
    """
    cmd = None
    user_data ="""#!/bin/bash
set -e -x
export DEBIAN_FRONTEND=noninteractive
apt-get --yes remove --force-yes freenx-server
apt-get install --force-yes freenx-server
"""
    #user_data = "apt-get install -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold'  -f -q -y freenx-server"

    # Create a connection to EC2 service.
    # You can pass credentials in to the connect_ec2 method explicitly
    # or you can use the default credentials in your ~/.boto config file
    # as we are doing here.
    ec2 = boto.connect_ec2()
    
    # Check to see if specified keypair already exists.
    # If we get an InvalidKeyPair.NotFound error back from EC2,
    # it means that it doesn't exist and we need to create it.
    try:
        key = ec2.get_all_key_pairs(keynames=[key_name])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidKeyPair.NotFound':
            print 'Creating keypair: %s' % key_name
            # Create an SSH key to use when logging into instances.
            key = ec2.create_key_pair(key_name)
            
            # AWS will store the public key but the private key is
            # generated and returned and needs to be stored locally.
            # The save method will also chmod the file to protect
            # your private key.
            key.save(key_dir)
        else:
            raise

    # Check to see if specified security group already exists.
    # If we get an InvalidGroup.NotFound error back from EC2,
    # it means that it doesn't exist and we need to create it.
    try:
        group = ec2.get_all_security_groups(groupnames=[group_name])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidGroup.NotFound':
            print 'Creating Security Group: %s' % group_name
            # Create a security group to control access to instance via SSH.
            group = ec2.create_security_group(group_name,
                                              'A group that allows SSH access')
        else:
            raise

    # Add a rule to the security group to authorize SSH traffic
    # on the specified port.
    try:
        group.authorize('tcp', ssh_port, ssh_port, cidr)
    except ec2.ResponseError, e:
        if e.code == 'InvalidPermission.Duplicate':
            print 'Security Group: %s already authorized' % group_name
        else:
            raise

    #find the volume for the user and class in question
    #volumes = ec2.get_all_volumes(filters={'tag-value': username, 'tag-value':classcode})
    #Attach the volume to the server
    #result = volumes.attach(instance, '/dev/sdf')
    #define user data to mount the volume
    # Now start up the instance.  The run_instances method
    # has many, many parameters but these are all we need
    # for now.
    reservation = ec2.run_instances(ami,
                                    key_name=key_name,
                                    security_groups=[group_name],
                                    instance_type=instance_type,
                                    user_data=user_data,
                                    placement=azone)

    # Find the actual Instance object inside the Reservation object
    # returned by EC2.

    instance = reservation.instances[0]
    machinename = classcode + "--" + username
    #Add user tags to it
    instance.add_tag('username', username)
    instance.add_tag('classcode', classcode)
    instance.add_tag('Name', machinename)

    # The instance has been launched but it's not yet up and
    # running.  Let's wait for its state to change to 'running'.

    print 'waiting for instance'
    while instance.state != 'running':
        print '.'
        time.sleep(5)
        instance.update()
    return 'Your instance has been created and is running at', instance.dns_name, '  Please use NX Viewer or remote desktop to connect.'

def list_instances(ami='ami-',
                   instance_type='t1.micro',
                   key_name='',
                   key_extension='.pem',
                   key_dir='~/.ssh',
                   group_name='vcl_lab',
                   ssh_port=22,
                   cidr='0.0.0.0/0',
                   tag='LBSC_670',
                   user_data=None,
                   cmd_shell=True,
                   login_user='ubuntu',
                   ssh_passwd=None,
                   username = '',
                   classcode='',
                   azone = 'us-east-1c'):         
        ec2 = boto.connect_ec2()
        reservations = ec2.get_all_instances(filters={'tag-value': username})
        machines = {}
        for reservation in reservations:
            instance = reservation.instances[0]
            instance_tags = instance.tags
            if instance_tags[u'Name']:    
                instance_name = instance_tags[u'Name']    
            else:
                instance_name = "Lab machine"
            if instance.state != 'terminated':
                tmpinstance = instance.image_id
                #comp_lab_info = {'lab_auth_info':'Sorry, I could not find any authentication information', 'lab_connection_options':'Sorry, I could not find connection options!'}
                try:
                    comp_lab_info = computerlab.objects.get(amazonami=tmpinstance)
                    lab_auth_info = comp_lab_info.lab_auth_info
                    connect_info = comp_lab_info.lab_connection_options  
                    coursecode = comp_lab_info.coursecode
                except Exception:
                    comp_lab_info = {'lab_auth_info':'simple', 'lab_connection_options':'test2'}
                    lab_auth_info = comp_lab_info['lab_auth_info']
                    coursecode = 'none'
                    connect_info = comp_lab_info['lab_connection_options']
                machines[instance.id] = {'instance_name': instance_name,'coursecode': coursecode, 'instance_type': instance.instance_type, 'lab_auth_info': lab_auth_info, 'instance_id': instance.id, 'connect_info': connect_info ,'instance_state': instance.state, 'ami_id': instance.image_id, 'public_dns': instance.public_dns_name}

        return machines

def start_instance(iid):         
    ec2 = boto.connect_ec2()
    reservations = ec2.get_all_instances(filters={'instance-id': iid})
    instance = reservations[0].instances[0]
    iid = [instance.id]
    instance_state = ec2.start_instances(iid)
    while instance.state != 'running':
        print '.'
        time.sleep(5)
        instance.update()

def stop_instance(iid):
    ec2 = boto.connect_ec2()
    reservations = ec2.get_all_instances(filters={'instance-id': iid})
    instance = reservations[0].instances[0]
    iid = [instance.id]
    instance_state = ec2.stop_instances(iid)
    while instance.state != 'stopped':
        print '.'
        time.sleep(5)
        instance.update()

def terminate_instance(iid):
    ec2 = boto.connect_ec2()
    reservations = ec2.get_all_instances(filters={'instance-id': iid})
    instance = reservations[0].instances[0]
    iid = [instance.id]
    instance_state = ec2.terminate_instances(iid)
    while instance.state != 'stopped':
        print '.'
        time.sleep(5)
        instance.update()

class MainPage(webapp.RequestHandler):
    
    def get(self):
        # Require authentication.
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        
        # Check if the user submitted an action
        action = 'Do Nothing'
#        if self.request.get("action") != '':
#            action = self.request.get("action")
#            if action == 'Start Server':
#                result = start_instance(iid)
#            if action == 'Stop Server':
#                result = stop_instance(iid)
#            if action == 'Create Server':
#                iitype = self.request.get('instance_type')
#                iid = self.request.get('iid')
#                coursecode = self.request.get('coursecode')
#                result = create_instance(username=user.nickname(), ami=iid, instance_type=iitype, classcode=coursecode)
#            if action == 'Terminate Server':
#                result = terminate_instance(iid)
#            if action == 'Download Connection File':
#                public_dns = request.POST['public_dns']
#                result = create_rdp_file(public_dns)
        list_of_machines = list_instances(username = user.nickname())
        list_of_labs = computerlab.all()
        
        # Construct dictionary of template variables.
        template_values = {
            'user': user,
            'login_url': users.create_login_url(self.request.uri),
            'logout_url': users.create_logout_url(self.request.uri),
            
            'list_of_machines': list_of_machines,
            'action': action,
            'list_of_labs': list_of_labs
        }
        
        # Render and write response to HTTP request.
        path = os.path.join(os.path.dirname(__file__), "./index.html") # Get path of index.html file
        rendered_text = template.render(path, template_values) # Render text for template
        self.response.out.write(rendered_text) # Send response containing index.html contents
    
    def post(self):
        # Require authentication.
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        
#        self.response.headers['Content-Type'] = 'text/plain'
#        self.response.out.write('Hello, webapp World!')

        # Check if user submitted an "iid", a VM instance ID.
        iid = self.request.get("iid", "")
        
        # Check if the user submitted an action
        action = self.request.get("action", "Do Nothing")
        
        # Process requested action
        if action != '' and iid != '':
            action = self.request.get("action")
            if action == 'Start Server':
                result = start_instance(iid)
            if action == 'Stop Server':
                result = stop_instance(iid)
            if action == 'Create Server':
                iitype = self.request.get('instance_type')
                iid = self.request.get('iid')
                coursecode = self.request.get('coursecode')
                result = create_instance(username=user.nickname(), ami=iid, instance_type=iitype, classcode=coursecode)
            if action == 'Terminate Server':
                result = terminate_instance(iid)
            if action == 'Download Connection File':
                public_dns = self.request.get('public_dns')
                result = create_rdp_file(public_dns)

        # List virtual machines (VMs) and labs (VCLs) in environment (VRE)
        list_of_machines = list_instances(username=user.nickname())
        list_of_labs = computerlab.all()
        
        template_values = {
            'user': user,
            'login_url': users.create_login_url(self.request.uri),
            'logout_url': users.create_logout_url(self.request.uri),
            
            'list_of_machines': list_of_machines,
            'action': action,
            'list_of_labs': list_of_labs
        }
        
        # Render and write response to HTTP request.
        path = os.path.join(os.path.dirname(__file__), "./index.html") # Get path of index.html file
        rendered_text = template.render(path, template_values) # Render text for template
        self.response.out.write(rendered_text) # Send response containing index.html contents

# e.g., ec2-50-17-78-170.compute-1.amazonaws.com
class create_rdp_file(webapp.RequestHandler):
    
    def get(self):
        # Require authentication.
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
    
        #import StringIO    
    #    import csv
        public_dns = self.request.get('public_dns')
    #    import cStringIO as StringIO
        #response = HttpResponse(tmpfile, content_type="application/x-rdp")
        #response['Content-Disposition'] = 'attachment; filename=connect.rdp'    
        #writer = csv.writer(response)
        #myfile = StringIO.StringIO(response)
        tmpfile = """ screen mode id:i:1
desktopwidth:i:1400
desktopheight:i:875
session bpp:i:16
auto connect:i:1
compression:i:1
keyboardhook:i:2
audiomode:i:2
redirectdrives:i:0
redirectprinters:i:0
redirectcomports:i:0
redirectsmartcards:i:0
displayconnectionbar:i:1
username:s:
domain:s:
alternate shell:s:
shell working directory:s:
disable wallpaper:i:1
disable full window drag:i:1
disable menu anims:i:1
disable themes:i:1
bitmapcachepersistenable:i:1
full address:s:%s
""" % (public_dns)

        #tmpfile = tmpfile+"full address:s:"+public_dns
        #writer.writerow([tmpfile])
#        response = HttpResponse(tmpfile, content_type="application/x-rdp")
#        response['Content-Disposition'] = 'attachment; filename=connect.rdp'
        
        self.response.headers['Content-Type'] = "application/x-rdp"
        self.response.headers['Content-Disposition'] = 'attachment; filename=connect.rdp'
        self.response.out.write(tmpfile)

application = webapp.WSGIApplication([
        ('/', MainPage),
        ('/downloadrdp', create_rdp_file)
    ], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
