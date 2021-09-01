from __future__ import unicode_literals

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from connection.exceptions import AlreadyExistsError
from connection.signals import (
    block_created,
    block_removed,
    followee_created,
    followee_removed,
    follower_created,
    follower_removed,
    following_created,
    following_removed,
    connection_removed,
    connection_request_accepted,
    connection_request_canceled,
    connection_request_created,
    connection_request_rejected,
    connection_request_viewed,
)

AUTH_USER_MODEL = getattr(settings, "AUTH_USER_MODEL", "auth.User")

CACHE_TYPES = {
    "connections": "c-%s",
    "followers": "fo-%s",
    "following": "fl-%s",
    "blocks": "b-%s",
    "blocked": "bo-%s",
    "blocking": "bd-%s",
    "requests": "cr-%s",
    "sent_requests": "scr-%s",
    "unread_requests": "cru-%s",
    "unread_request_count": "cruc-%s",
    "read_requests": "crr-%s",
    "rejected_requests": "crj-%s",
    "unrejected_requests": "crur-%s",
    "unrejected_request_count": "crurc-%s",
}

BUST_CACHES = {
    "connections": ["connections"],
    "followers": ["followers"],
    "blocks": ["blocks"],
    "blocked": ["blocked"],
    "following": ["following"],
    "blocking": ["blocking"],
    "requests": [
        "requests",
        "unread_requests",
        "unread_request_count",
        "read_requests",
        "rejected_requests",
        "unrejected_requests",
        "unrejected_request_count",
    ],
    "sent_requests": ["sent_requests"],
}


def cache_key(type, user_pk):
    """
    Build the cache key for a particular type of cached value
    """
    return CACHE_TYPES[type] % user_pk


def bust_cache(type, user_pk):
    """
    Bust our cache for a given type, can bust multiple caches
    """
    bust_keys = BUST_CACHES[type]
    keys = [CACHE_TYPES[k] % user_pk for k in bust_keys]
    cache.delete_many(keys)


class ConnectionRequest(models.Model):
    """ Model to represent connection requests """

    from_user = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connection_requests_sent",
    )
    to_user = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connection_requests_received",
    )

    message = models.TextField(_("Message"), blank=True)

    created = models.DateTimeField(default=timezone.now)
    rejected = models.DateTimeField(blank=True, null=True)
    viewed = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _("Connection Request")
        verbose_name_plural = _("Connection Requests")
        unique_together = ("from_user", "to_user")

    def __str__(self):
        return "%s" % self.from_user_id

    def accept(self):
        """ Accept this connection request """
        Contact.objects.create(from_user=self.from_user, to_user=self.to_user)

        Contact.objects.create(from_user=self.to_user, to_user=self.from_user)

        connection_request_accepted.send(
            sender=self, from_user=self.from_user, to_user=self.to_user
        )

        self.delete()

        # Delete any reverse requests
        ConnectionRequest.objects.filter(
            from_user=self.to_user, to_user=self.from_user
        ).delete()

        # Bust requests cache - request is deleted
        bust_cache("requests", self.to_user.pk)
        bust_cache("sent_requests", self.from_user.pk)
        # Bust reverse requests cache - reverse request might be deleted
        bust_cache("requests", self.from_user.pk)
        bust_cache("sent_requests", self.to_user.pk)
        # Bust connections cache - new connections added
        bust_cache("connections", self.to_user.pk)
        bust_cache("connections", self.from_user.pk)

        return True

    def reject(self):
        """ reject this connection request """
        self.rejected = timezone.now()
        self.delete()
        connection_request_rejected.send(sender=self)
        bust_cache("requests", self.to_user.pk)
        bust_cache("sent_requests", self.from_user.pk)
        return True

    def cancel(self):
        """ cancel this connection request """
        self.delete()
        connection_request_canceled.send(sender=self)
        bust_cache("requests", self.to_user.pk)
        bust_cache("sent_requests", self.from_user.pk)

        bust_cache("requests", self.from_user.pk)
        bust_cache("sent_requests", self.to_user.pk)

        return True

    def mark_viewed(self):
        self.viewed = timezone.now()
        connection_request_viewed.send(sender=self)
        self.save()
        bust_cache("requests", self.to_user.pk)
        return True


class ConnectionManager(models.Manager):
    """ Connection manager """

    def suppliers(self, from_user):

        """ Return a list of all suppliers """
        suppliers = Contact.objects.filter(from_user = from_user , is_supplier = True)
        sup = []
        for x in suppliers:
            sup.append(x.to_user)
        return sup

    def costumers(self, from_user):
        """ Return a list of all costumers """
        costumers = Contact.objects.filter(from_user = from_user , is_costumer = True)
        cos = []
        for x in costumers:
            cos.append(x.to_user)
        return cos

    def connections(self, user):
        """ Return a list of all connections """
        key = cache_key("connections", user.pk)
        connections = cache.get(key)

        if connections is None:
            qs = (
                Contact.objects.select_related("from_user", "to_user")
                .filter(to_user=user)
                .all()
            )
            connections = [u.from_user for u in qs]
            cache.set(key, connections)

        return connections


    def requests(self, user):
        """ Return a list of connection requests """
        key = cache_key("requests", user.pk)
        requests = cache.get(key)

        if requests is None:
            qs = (
                ConnectionRequest.objects.select_related("from_user", "to_user")
                .filter(to_user=user)
                .all()
            )
            requests = list(qs)
            cache.set(key, requests)

        return requests

    def sent_requests(self, user):
        """ Return a list of connection requests from user """
        key = cache_key("sent_requests", user.pk)
        requests = cache.get(key)

        if requests is None:
            qs = (
                ConnectionRequest.objects.select_related("from_user", "to_user")
                .filter(from_user=user)
                .all()
            )
            requests = list(qs)
            cache.set(key, requests)

        return requests

    def unread_requests(self, user):
        """ Return a list of unread connection requests """
        key = cache_key("unread_requests", user.pk)
        unread_requests = cache.get(key)

        if unread_requests is None:
            qs = (
                ConnectionRequest.objects.select_related("from_user", "to_user")
                .filter(to_user=user, viewed__isnull=True)
                .all()
            )
            unread_requests = list(qs)
            cache.set(key, unread_requests)

        return unread_requests

    def unread_request_count(self, user):
        """ Return a count of unread connection requests """
        key = cache_key("unread_request_count", user.pk)
        count = cache.get(key)

        if count is None:
            count = (
                ConnectionRequest.objects.select_related("from_user", "to_user")
                .filter(to_user=user, viewed__isnull=True)
                .count()
            )
            cache.set(key, count)

        return count

    def read_requests(self, user):
        """ Return a list of read connection requests """
        key = cache_key("read_requests", user.pk)
        read_requests = cache.get(key)

        if read_requests is None:
            qs = (
                ConnectionRequest.objects.select_related("from_user", "to_user")
                .filter(to_user=user, viewed__isnull=False)
                .all()
            )
            read_requests = list(qs)
            cache.set(key, read_requests)

        return read_requests

    def rejected_requests(self, user):
        """ Return a list of rejected connection requests """
        key = cache_key("rejected_requests", user.pk)
        rejected_requests = cache.get(key)

        if rejected_requests is None:
            qs = (
                ConnectionRequest.objects.select_related("from_user", "to_user")
                .filter(to_user=user, rejected__isnull=False)
                .all()
            )
            rejected_requests = list(qs)
            cache.set(key, rejected_requests)

        return rejected_requests

    def unrejected_requests(self, user):
        """ All requests that haven't been rejected """
        key = cache_key("unrejected_requests", user.pk)
        unrejected_requests = cache.get(key)

        if unrejected_requests is None:
            qs = (
                ConnectionRequest.objects.select_related("from_user", "to_user")
                .filter(to_user=user, rejected__isnull=True)
                .all()
            )
            unrejected_requests = list(qs)
            cache.set(key, unrejected_requests)

        return unrejected_requests

    def unrejected_request_count(self, user):
        """ Return a count of unrejected connection requests """
        key = cache_key("unrejected_request_count", user.pk)
        count = cache.get(key)

        if count is None:
            count = (
                ConnectionRequest.objects.select_related("from_user", "to_user")
                .filter(to_user=user, rejected__isnull=True)
                .count()
            )
            cache.set(key, count)

        return count

    def add_connection(self, from_user, to_user, message=None):
        """ Create a connection request """
        if from_user == to_user:
            raise AlreadyExistsError("Users cannot contact themselves")

        if self.are_connections(from_user, to_user):
            raise AlreadyExistsError("You are already connections")

        if (ConnectionRequest.objects.filter(from_user=from_user, to_user=to_user).exists()):
            raise AlreadyExistsError("You already requested connection from this user.")

        if (ConnectionRequest.objects.filter(from_user=to_user, to_user=from_user).exists()):
            raise AlreadyExistsError("This user already requested connection from you.")

        if message is None:
            message = ""

        request, created = ConnectionRequest.objects.get_or_create(
            from_user=from_user, to_user=to_user
        )

        if created is False:
            raise AlreadyExistsError("Connection already requested")

        if message:
            request.message = message
            request.save()

        bust_cache("requests", to_user.pk)
        bust_cache("sent_requests", from_user.pk)
        connection_request_created.send(sender=request)

        return request

    def remove_supplier(self ,from_user, to_user):
        """ Remove a supplier """

        try:
            connection = Contact.objects.get(from_user=from_user, to_user=to_user)
            connection.is_supplier = False
            connection.save()
            return True
        except Contact.DoesNotExist:
            return False

    def remove_costumer(self ,from_user, to_user):
        """ Remove a costumer """
        try:
            connection = Contact.objects.get(from_user=from_user, to_user=to_user)
            connection.is_costumer = False
            connection.save()
            return True
        except Contact.DoesNotExist:
            return False

    def remove_connection(self, from_user, to_user):
        """ Destroy a connection relationship """
        try:
            qs = Contact.objects.filter(Q(to_user=to_user, from_user=from_user) | Q(to_user=from_user, from_user=to_user))
            distinct_qs = qs.distinct().all()

            if distinct_qs:
                connection_removed.send(
                    sender=distinct_qs[0], from_user=from_user, to_user=to_user
                )
                qs.delete()
                bust_cache("connections", to_user.pk)
                bust_cache("connections", from_user.pk)
                bust_cache("sent_requests", to_user.pk)
                bust_cache("sent_requests", from_user.pk)

                return True
            else:
                return False
        except Contact.DoesNotExist:
            return False

    def are_connections(self, user1, user2):
        """ Are these two users connections? """
        connections1 = cache.get(cache_key("connections", user1.pk))
        connections2 = cache.get(cache_key("connections", user2.pk))
        if connections1 and user2 in connections1:
            return True
        elif connections2 and user1 in connections2:
            return True
        else:
            try:
                Contact.objects.get(to_user=user1, from_user=user2)
                return True
            except Contact.DoesNotExist:
                return False

class Contact(models.Model):
    """ Model to represent Connections """

    to_user = models.ForeignKey(AUTH_USER_MODEL, models.CASCADE, related_name="connections")
    from_user = models.ForeignKey(
        AUTH_USER_MODEL, models.CASCADE, related_name="_unused_connection_relation"
    )
    created = models.DateTimeField(default=timezone.now)

    # to_user is supplier
    is_supplier = models.BooleanField(default=False)

    # to_user is costumer
    is_costumer = models.BooleanField(default=False)

    objects = ConnectionManager()

    class Meta:
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")
        unique_together = ("from_user", "to_user")

    def __str__(self):
        return "User #%s is connections with #%s" % (self.to_user_id, self.from_user_id)

    def save(self, *args, **kwargs):
        # Ensure users can't be connections with themselves
        if self.to_user == self.from_user:
            raise ValidationError("Users cannot be connections with themselves.")
        super(Contact, self).save(*args, **kwargs)


class FollowingManager(models.Manager):
    """ Following manager """

    def followers(self, user):
        """ Return a list of all followers """
        key = cache_key("followers", user.pk)
        followers = cache.get(key)

        if followers is None:
            qs = Follow.objects.filter(followee=user).all()
            followers = [u.follower for u in qs]
            cache.set(key, followers)

        return followers

    def following(self, user):
        """ Return a list of all users the given user follows """
        key = cache_key("following", user.pk)
        following = cache.get(key)

        if following is None:
            qs = Follow.objects.filter(follower=user).all()
            following = [u.followee for u in qs]
            cache.set(key, following)

        return following

    def add_follower(self, follower, followee):
        """ Create 'follower' follows 'followee' relationship """
        if follower == followee:
            raise ValidationError("Users cannot follow themselves")

        relation, created = Follow.objects.get_or_create(
            follower=follower, followee=followee
        )

        if created is False:
            raise AlreadyExistsError(
                "User '%s' already follows '%s'" % (follower, followee)
            )

        follower_created.send(sender=self, follower=follower)
        followee_created.send(sender=self, followee=followee)
        following_created.send(sender=self, following=relation)

        bust_cache("followers", followee.pk)
        bust_cache("following", follower.pk)

        return relation

    def remove_follower(self, follower, followee):
        """ Remove 'follower' follows 'followee' relationship """
        try:
            rel = Follow.objects.get(follower=follower, followee=followee)
            follower_removed.send(sender=rel, follower=rel.follower)
            followee_removed.send(sender=rel, followee=rel.followee)
            following_removed.send(sender=rel, following=rel)
            rel.delete()
            bust_cache("followers", followee.pk)
            bust_cache("following", follower.pk)
            return True
        except Follow.DoesNotExist:
            return False

    def follows(self, follower, followee):
        """ Does follower follow followee? Smartly uses caches if exists """
        followers = cache.get(cache_key("following", follower.pk))
        following = cache.get(cache_key("followers", followee.pk))

        if followers and followee in followers:
            return True
        elif following and follower in following:
            return True
        else:
            return Follow.objects.filter(follower=follower, followee=followee).exists()


class Follow(models.Model):
    """ Model to represent Following relationships """

    follower = models.ForeignKey(
        AUTH_USER_MODEL, models.CASCADE, related_name="following"
    )
    followee = models.ForeignKey(
        AUTH_USER_MODEL, models.CASCADE, related_name="followers"
    )
    created = models.DateTimeField(default=timezone.now)

    objects = FollowingManager()

    class Meta:
        verbose_name = _("Following Relationship")
        verbose_name_plural = _("Following Relationships")
        unique_together = ("follower", "followee")

    def __str__(self):
        return "User #%s follows #%s" % (self.follower_id, self.followee_id)

    def save(self, *args, **kwargs):
        # Ensure users can't be connections with themselves
        if self.follower == self.followee:
            raise ValidationError("Users cannot follow themselves.")
        super(Follow, self).save(*args, **kwargs)


class BlockManager(models.Manager):
    """ Following manager """

    def blocked(self, user):
        """ Return a list of all blocks """
        key = cache_key("blocked", user.pk)
        blocked = cache.get(key)

        if blocked is None:
            qs = Block.objects.filter(blocked=user).all()
            blocked = [u.blocked for u in qs]
            cache.set(key, blocked)

        return blocked

    def blocking(self, user):
        """ Return a list of all users the given user blocks """
        key = cache_key("blocking", user.pk)
        blocking = cache.get(key)

        if blocking is None:
            qs = Block.objects.filter(blocker=user).all()
            blocking = [u.blocked for u in qs]
            cache.set(key, blocking)

        return blocking

    def add_block(self, blocker, blocked):
        """ Create 'follower' follows 'followee' relationship """
        if blocker == blocked:
            raise ValidationError("Users cannot block themselves")

        relation, created = Block.objects.get_or_create(
            blocker=blocker, blocked=blocked
        )

        if created is False:
            raise AlreadyExistsError(
                "User '%s' already blocks '%s'" % (blocker, blocked)
            )

        block_created.send(sender=self, blocker=blocker)
        block_created.send(sender=self, blocked=blocked)
        block_created.send(sender=self, blocking=relation)

        bust_cache("blocked", blocked.pk)
        bust_cache("blocking", blocker.pk)

        return relation

    def remove_block(self, blocker, blocked):
        """ Remove 'blocker' blocks 'blocked' relationship """
        try:
            rel = Block.objects.get(blocker=blocker, blocked=blocked)
            block_removed.send(sender=rel, blocker=rel.blocker)
            block_removed.send(sender=rel, blocked=rel.blocked)
            block_removed.send(sender=rel, blocking=rel)
            rel.delete()
            bust_cache("blocked", blocked.pk)
            bust_cache("blocking", blocker.pk)
            return True
        except Block.DoesNotExist:
            return False

    def is_blocked(self, user1, user2):
        """ Are these two users blocked? """
        block1 = cache.get(cache_key("blocks", user1.pk))
        block2 = cache.get(cache_key("blocks", user2.pk))
        if block1 and user2 in block1:
            return True
        elif block2 and user1 in block2:
            return True
        else:
            try:
                Block.objects.get(blocker=user1, blocked=user2)
                return True
            except Block.DoesNotExist:
                return False


class Block(models.Model):
    """ Model to represent Following relationships """

    blocker = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocking"
    )
    blocked = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blockees"
    )
    created = models.DateTimeField(default=timezone.now)

    objects = BlockManager()

    class Meta:
        verbose_name = _("Blocked Relationship")
        verbose_name_plural = _("Blocked Relationships")
        unique_together = ("blocker", "blocked")

    def __str__(self):
        return "User #%s blocks #%s" % (self.blocker_id, self.blocked_id)

    def save(self, *args, **kwargs):
        # Ensure users can't be connections with themselves
        if self.blocker == self.blocked:
            raise ValidationError("Users cannot block themselves.")
        super(Block, self).save(*args, **kwargs)
