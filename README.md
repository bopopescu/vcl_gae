Virtual Research Environment
============================

## Set up Development Environment

To configure Amazon Web Services (AWS), specify your AWS Access Key ID and AWS Secret Access Key in the file

	settings.py

If this file does not exist, create it, and copy and paste the following code into it.

	def init_boto(config):
		config.add_section('Credentials')
		config.set('Credentials', 'aws_access_key_id', '')
		config.set('Credentials', 'aws_secret_access_key', '')

The AWS Access Key ID can be specified by setting the key ``aws_access_key_id`` and the AWS Secret Access Key can be specified by setting it to ``aws_secret_access_key``.  For example, if your AWS Access Key ID is ``022QF06E7MXBSAMPLE`` and your AWS Secret Access Key is ``kWcrlUX5JEDGM/SAMPLE/aVmYvHNif5zB+d9+ct``.

	def init_boto(config):
		config.add_section('Credentials')
		config.set('Credentials', 'aws_access_key_id', '022QF06E7MXBSAMPLE')
		config.set('Credentials', 'aws_secret_access_key', 'kWcrlUX5JEDGM/SAMPLE/aVmYvHNif5zB+d9+ct')