## Builing the RPM locally

```shell script
cd ci/rpm
cp .env-sample .env  # and optionally edit if needed to match your current user's UID/GID
docker-compose up --build rpm
# the artifacts will be located in dist/ folder in top-level project directory
```
