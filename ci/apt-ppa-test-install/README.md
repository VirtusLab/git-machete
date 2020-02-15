## Test the availability of the uploaded package

```shell script
cd ci/apt-ppa-test-install/
docker-compose up --build --exit-code-from=apt-ppa-test-install apt-ppa-test-install
```
