## Test the availability of the uploaded package

```shell script
cd ci/deb-ppa-test-install/
docker-compose up --build --exit-code-from=deb-ppa-test-install deb-ppa-test-install
```
