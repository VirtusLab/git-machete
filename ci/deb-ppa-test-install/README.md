## Test the availability of the uploaded package

```shell script
cd ci/deb-ppa-test-install/
export UBUNTU_VERSION=18.04  # or 20.04 or 22.04
docker-compose build deb-ppa-test-install
docker-compose run deb-ppa-test-install
```
