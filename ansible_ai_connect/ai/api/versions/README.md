
## Versioning principles and restrictions:

The application API is organized by versions directory structure, that rely on some basic principles and restrictions:

- The views and serializers outside the versions directories is considered as base code,
in the future the related modules should be moved to a base directory.

- urls modules use views that are imported only from the same version directory hierarchy.
- urls modules use urls to include that are imported only from the same version directory hierarchy,
an exception is made for urls to include from external application.

- views modules can use serializers that are imported only from the same version directory hierarchy.

views modules of a version x can:
- reuse the base views, directly or modified (using inheritance).
- reuse the views only from the previous x-1 version, directly or modified (using inheritance).

serializers modules of a version x can:
- reuse the base serializers, directly or modified (using inheritance).
- reuse the serializers only from the previous x-1 version, directly or modified (using inheritance).

## Generate a concrete API schema version

```commandline
VERSION="v1" podman exec -it --user=0 docker-compose-django-1 wisdom-manage spectacular --api-version $VERSION --file /var/www/ansible-ai-connect-service/ansible_ai_connect/schema-$VERSION.yaml
```
This will generate a schema file with requested version at ansible_ai_connect directory

the default format is openapi (yaml file format)
but also openapi-json can be produced with "--format openapi-json" option
