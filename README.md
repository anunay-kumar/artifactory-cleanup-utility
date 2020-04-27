
# Artifactory Cleanup Utility

This utility cleans up the artifactory repos and associated paths based on the artifactory.yaml config file found in the same directory as this script. It requires Python3. The idea is to periodically run this utility as a cron job or a jenkins job. This utility is configured using a yaml file (artifactory.yaml). This yaml file lists down the repos and their corresponding paths that need to be cleaned up. There is a retention period that is specified for each repo which retains the files created within that period.

```
Usage: maintain_artifactory.py [options] --dryrun or --production
--dryrun: Generate a log report of all the changes that will be done
--production: Run in production mode, cleanup all the files
```


> How to restore a directory from recycle repo? <

We copy all the artifacts to the recycle repo before deleting them so in an unfortunate event if something gets deleted by mistake, it can be restored from the recycle bin. There is a copy REST api that can be used to copy the deleted folders/files back to the repo. 

 - Example using curl:
```bash
curl -X POST -H "X-JFrog-Art-Api:<API_KEY>" https://art-host.com/artifactory/api/copy/<recycle_repo>/<recycled_folder_file_path>?to=/<restore_repo>/<path_where_to_restore>&dry=1
```

```bash
curl -v -X POST -H "X-JFrog-Art-Api:<API_KEY" "https://art-host.com/artifactory/api/copy \
/art-recycle-generic-local/builds/dev/HelloWorld/20200421-1413_HelloWorld_100_TEST_PERSONAL?to= \
/art-mint-generic-local/builds/dev/HelloWorld/20200421-1413_HelloWorld_100_TEST_PERSONAL&dry=1"
```
##### Note: dry=1 in the url runs in dry-run mode, dry=0 runs in live mode
