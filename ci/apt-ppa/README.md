## Automated PPA upload

```shell script
cd ci/apt-ppa
cp .env-sample .env  # and optionally edit if needed to match your current user's UID/GID
. upload-export-vars
docker-compose up --build ppa-upload
```


## Test the availability of the uploaded package

```shell script
cd ci/apt-ppa
docker-compose up --build ppa-test-install
```
