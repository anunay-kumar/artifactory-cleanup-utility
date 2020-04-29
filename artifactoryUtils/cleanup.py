'''
# Author: Anunay Kumar
# Desc: Module to maintain artifactory uploads
'''

import sys,os,http,requests,json,logging,yaml,datetime
requests.packages.urllib3.disable_warnings()

# Set Logger
logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s][%(name)s] %(levelname)s  %(message)s', "%Y-%m-%d %H:%M:%S")
ch.setFormatter(formatter)
logger.addHandler(ch)


class utils:

    def __init__(self):
        self.art_host = 'https://eu.artifactory.swg-devops.com/artifactory/'
        self.src_repo = None
        self.dst_repo = None
        self.recycle_repo = None
        self.src_path = None
        self.dst_path = None
        self.action = None
        self.retention_period = None
        self.config_file = None
        self.artifact_type = None
        self.skip_list = None

        if "ART_API" in os.environ:
            self.art_key = os.getenv("ART_API")
        else:
            print("Missing environment variable 'ART_API'. Please set the variable and rerun.")
            sys.exit(1)

    def aqlDeleteList(self):
        logger.debug(self.src_path)
        # AQL finds items modified older than self.retention_period
        aql = 'items.find( \
                    { \
                        "type":"%s", \
                        "repo": "%s", \
                        "modified":{"$before" : "%s"}, \
                        "path":"%s" \
                    } \
                )'%(self.artifact_type,self.src_repo,self.retention_period,self.src_path)
        
        logger.debug('AQL: ' + aql)
        return aql.replace(' ','')

    # Return list of artifacts to be deleted
    def getDeleteList(self):
        logger.info("[Get-Delete-List] Getting list of folder/files to be deleted...")

        # REST call
        head = {'Content-Type': 'text/plain', 'Accept': 'application/json', 'X-JFrog-Art-Api': self.art_key}
        ret = requests.post(self.art_host + 'api/search/aql',
                            data=self.aqlDeleteList(),
                            headers=head,
                            verify=False)
        logger.debug(ret)
        logger.debug(ret.json())
        if ret.status_code != 200:
            logger.info(ret)
            logger.info(ret.json())
            logger.critical("Failed to retrieve list")
            sys.exit(1)
        return ret.json()

    # Copy artifacts to the recycle repo
    def copyItemsToRecycleBin(self, isDryRun, artifact_repo, artifact_path):
        if isDryRun is True:
            dry_run = '&dry=1'
        else:
            dry_run = '&dry=0'

        # REST call
        head = {'Content-Type': 'text/plain', 'Accept': 'application/json', 'X-JFrog-Art-Api': self.art_key}
        api_url = self.art_host + 'api/copy/' + artifact_repo + '/' + artifact_path + '?to=/' + self.recycle_repo + '/' + artifact_path + dry_run
        logger.info('|   |-- Copy-To-Recycle ' + api_url)
        ret = requests.post(api_url,
                            headers=head,
                            verify=False)
        if ret.status_code == 200:
            logger.info('|   |-- Copy-To-Recycle ' + str(json.loads(json.dumps(ret.json()))['messages'][0]))
            logger.info('|   |-- Copy-To-Recycle Done')
        else:
            logger.warning(ret)
            logger.warning(ret.content)
            logger.critical("    |-- Copy-To-Recycle Error")
            sys.exit(1)

    #Delete artifacts
    def deleteItemsfromRepo(self, isDryRun, artifact_repo, artifact_path):
        # REST call
        head = {'Content-Type': 'text/plain', 'Accept': 'application/json', 'X-JFrog-Art-Api': self.art_key}
        api_url = self.art_host + artifact_repo + '/' + artifact_path + '?to=/' + self.recycle_repo + '/' + artifact_path
        logger.info('|   |-- Delete-Artifact ' + api_url)

        if isDryRun is True:
            logger.info('|   |-- Delete-Artifact DRY RUN Done')
            return

        ret = requests.delete(api_url,
                            headers=head,
                            verify=False)
        if ret.status_code == 204: # For successful delete operation server sends back 'No content' 204 status
            logger.info('|   |-- Delete-Artifact ' + 'status_code is ' + str(ret.status_code))
            logger.info('|   |-- Delete-Artifact Done')
        else:
            logger.warning(ret)
            logger.warning(ret.content)
            logger.critical('|   |-- Delete-Artifact Error')
            sys.exit(1)

    # Prevent critical paths from being configured for delete
    def validatePath(self, artifact_path):
        # Prevent critical paths from getting deleted
        if artifact_path in self.skip_list:
            logger.critical("[Validate-Path] Path not allowed to be deleted: '" + artifact_path + "'. Matched skip_list - '" + str(self.skip_list))
            sys.exit(1)
        else:
            logger.debug("[Validate-Path] Valid path: '" + artifact_path + "' not in skip_list - '" + str(self.skip_list))

    def uploadfile(self, artifact_repo, artifact_path, artifact_file):
        # REST call
        head = {'Content-Type': 'text/plain', 'Accept': 'application/json', 'X-JFrog-Art-Api': self.art_key}
        api_url = self.art_host + artifact_repo + '/' + artifact_path + '/' + os.path.basename(artifact_file)
        files = {'file': open(artifact_file, 'rb')}
        logger.info('Uploading...' + api_url)
        ret = requests.put(api_url,
                            headers=head,
                            files = files,
                            verify=False)
        if ret.status_code == 201:
            logger.info('File uploaded...')
        else:
            logger.warning(ret)
            logger.warning(ret.content)
            logger.critical("Failed to upload file...")
            sys.exit(1)

    def upload_logs(self, repo, path, file):
        logger.info('Uploading logs...' + file)
        self.uploadfile(repo, path, file)

    # This method is the controller method that manages the entire cleanup cycle
    def clean(self, isDryRun, src_repo, src_path, retention_period, recycle_repo='', copy=True, delete=True):
        self.src_repo = src_repo
        self.dst_repo = None
        self.recycle_repo = recycle_repo
        if 'file' in src_path.lower():
            self.artifact_type = 'file'
            self.src_path = src_path.split('|')[0]
        else:
            self.artifact_type = 'folder'
            self.src_path = src_path

        self.dst_path = None
        self.retention_period = retention_period
        logger.info("")
        logger.info("==============================================")
        logger.info("Cleaning Artifactory")
        logger.info("==============================================")
        logger.info('Source Repo: ' + self.src_repo)
        logger.info('Source Path: ' + self.src_path)
        logger.info('Recycle Repo: ' + self.recycle_repo)
        logger.info('Search Type: ' + self.artifact_type)
        logger.info('Retention Period: ' + self.retention_period)
        logger.info('Copy: ' + str(copy) + ' Delete: ' + str(delete))
        logger.info('Delete Artifacts Before/On: ' + str(datetime.date.today() - datetime.timedelta(int(self.retention_period[0:len(self.retention_period) - 1]))))
        logger.info("==============================================")

        # Validate incoming path
        self.validatePath(self.src_path)

        items=json.loads(json.dumps(self.getDeleteList())) # Retrieve the delete candidate artifacts
        logger.debug(items)
        path_num = len(items['results'])
        i = 0
        if path_num>0:
            for item in items['results']: # Iterate through the artifacts to delete
                i += 1
                logger.debug(item)
                artifact_url = self.art_host + item['repo'] + '/' + item['path'] + '/' + item['name']
                artifact_repo = item['repo']
                artifact_path = item['path'] + '/' + item['name']
                logger.info('|-- Processing-File-' + str(i) + ' ' + artifact_url)
                if copy is True: # Copy to recycle repo before delete
                    self.copyItemsToRecycleBin(isDryRun, artifact_repo, artifact_path)
                if delete is True: # Delete the artifacts
                    self.deleteItemsfromRepo(isDryRun, artifact_repo, artifact_path)
            logger.info('[Get-Delete-List] >>>> Processed ' + str(path_num) + ' path(s) successfully <<<<')
        else:
            logger.warning('[Get-Delete-List] >>>> No folder/file path(s) found for removal <<<<')
