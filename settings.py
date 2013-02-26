def init_boto(config):
    config.add_section('Credentials')
    config.set('Credentials', 'aws_access_key_id', '')
    config.set('Credentials', 'aws_secret_access_key', '')