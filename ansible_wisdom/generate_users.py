import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from faker import Faker
from rest_framework.authtoken.models import Token

fake = Faker()

group_name = "perf"
requested_users = 1000


def get_or_create_group(group_name):
    try:
        group_obj = Group.objects.get(name__iexact=group_name)
    except Group.DoesNotExist:
        group_obj = Group.objects.create(name=group_name)
    return group_obj


def list_group_users(group_name, print_token):
    group = get_or_create_group(group_name)
    users = group.user_set.all()
    print(f"Users in group {group_name}:")
    for user in users:
        print(f"{user.username},{Token.objects.get(user=user) if print_token else '***'}")


def count_group_users(group_name):
    group = get_or_create_group(group_name)
    return group.user_set.count()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.LazyAttribute(lambda _: fake.user_name())
    email = factory.LazyAttribute(lambda _: fake.email())
    first_name = 'TEST'
    last_name = 'USER'

    @factory.post_generation
    def add_to_group(obj, create, extracted, **kwargs):
        if create:
            obj.groups.add(get_or_create_group("perf"))


needed_users = requested_users - count_group_users(group_name)
for _ in range(needed_users):
    user = UserFactory.create()

list_group_users(group_name, True)
