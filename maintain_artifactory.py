"""
Author: Anunay Kumar
Desc: Module to maintain artifactory uploads

Usage: maintain_artifactory.py [options] --dryrun or --production
--dryrun: Generate a log report of all the changes that will be done
--production: Run in production mode, cleanup all the files
This script cleans up the artifactory repos and associated paths based on the artifactory.yaml
file found in the same directory as this script. It requires Python3."

>> How to restore a directory from recycle repo? <<

We copy all the artifacts to the recycle repo before deleting them so in an unfortunate event if
something gets deleted by mistake, it can be restored from the recycle bin. There is a move REST
api that can be used to copy the deleted folders/files back to the repo. Example using curl:

curl -X POST -H "X-JFrog-Art-Api:<API_KEY>" https://art-host.com/artifactory/api/copy/<recycle_repo>/<recycled_folder_file_path>?to=/<restore_repo>/<path_where_to_restore>&dry=1

curl -v -X POST -H "X-JFrog-Art-Api:<API_KEY" "https://art-host.com/artifactory/api/copy \
/art-recycle-generic-local/builds/dev/HelloWorld/20200421-1413_HelloWorld_100_TEST_PERSONAL?to= \
/art-mint-generic-local/builds/dev/HelloWorld/20200421-1413_HelloWorld_100_TEST_PERSONAL&dry=1"

** dry=1 in the url runs in dry-run mode, dry=0 runs in live mode
"""

import logging,os,datetime,yaml,json
from artifactoryUtils import *
from optparse import OptionParser

util = cleanup.utils()

# Set logger
now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = os.getcwd() + '/cleanup_' + now + '.log'

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s][%(name)s] %(levelname)s  %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename = log_file)
ch = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s][%(name)s] %(levelname)s  %(message)s', "%Y-%m-%d %H:%M:%S")
ch.setFormatter(formatter)
logger.addHandler(ch)


def run(isDryRun):
    logger.info("----Starting----")

    with open(util.config_file, 'r') as file:
        artifactory = yaml.full_load(file)
        logger.debug('>> Parsing YAML file for cleanup paths:')
        logger.debug('Yaml: ' + json.dumps(artifactory))
        recycle_repo = artifactory['recycle']
        util.skip_list = artifactory['skip_list']
        for repo in artifactory['repos']:
                retention = artifactory['repos'][repo]['retention']
                logger.debug('Repo: ' + repo)
                logger.debug(' + Retention: ' + artifactory['repos'][repo]['retention'])
                for path in artifactory['repos'][repo]['paths']:
                    logger.debug(' + Path: ' + path)
                    util.clean(isDryRun, repo, path, retention, recycle_repo)
    logger.info("------Done------")
    util.upload_logs(recycle_repo, 'runlogs', log_file)


# Parse the input options
parser = OptionParser(
    usage="Usage: %prog [options] --dryrun or --production or --config-file\n \
    --dryrun: Generate a log report of all the changes that will be done\n \
    --production: Run in production mode, cleanup all the files \n \
    --config-file: Pass the the config file, default is artifactory.yaml \n \
    This script cleans up the artifactory repos and associated paths based on the artifactory.yaml file \n \
    found in the same directory as this script. It requires Python3.",
    version="%prog 1.0")

parser.add_option("--dryrun", dest="dryrun", action="store_true", default=False, help="Dry run and verify the delete report")
parser.add_option("--production", dest="production", action="store_true", default=False, help="Run in production mode, changes will be made")
parser.add_option("--config-file", dest="config_file", default='artifactory.yaml', help="Pass the the config file, default is artifactory.yaml")

(options, args) = parser.parse_args()

util.config_file = os.path.abspath(options.config_file)

if options.dryrun:
    logger.info('Running in ------DRY RUN MODE/NO CHANGES WILL BE MADE------')
    run(isDryRun=True)
elif options.production:
    logger.info('Running in ------PRODUCTION MODE/CHANGES WILL BE MADE------')
    run(isDryRun=False)
else:
    parser.error("Wrong number of arguments. Usage: " + os.path.basename(__file__) + " [options] --dryrun or --production or --help")
