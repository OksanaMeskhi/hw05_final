import shutil
import tempfile

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.paginator import Page
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from posts.forms import PostForm, CommentForm
from posts.models import Comment, Follow, Group, Post, User

User = get_user_model()
PAGE_SIZE_2 = 3
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='author')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
            description='Тестовое описание',
        )
        cls.small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00'
            b'\x01\x00\x00\x00\x00\x21\xf9\x04'
            b'\x01\x0a\x00\x01\x00\x2c\x00\x00'
            b'\x00\x00\x01\x00\x01\x00\x00\x02'
            b'\x02\x4c\x01\x00\x3b'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.small_gif,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
            group=cls.group,
            image=cls.uploaded,
        )
        cls.comment = Comment.objects.create(
            post=cls.post,
            author=cls.post.author,
            text='Тестовый комментарий',
        )

        cls.form_fields = {
            'text': forms.fields.CharField,
        }

    def setUp(self):
        self.guest = Client()
        self.authorized = Client()
        self.authorized.force_login(PostViewsTest.user)
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def context_test(self, post):
        self.assertIsInstance(post, Post)
        self.assertEqual(post.text, self.post.text)
        self.assertEqual(post.author.username, self.user.username)
        self.assertEqual(post.group.slug, self.group.slug)
        self.assertEqual(post.image, f'posts/{self.uploaded}')

    def get_post(self, response):
        page_obj = response.context.get('page_obj')
        self.assertIsInstance(page_obj, Page)
        return page_obj[0]

    def test_index_page_show_correct_context(self):
        response = self.authorized.get(reverse('posts:index'))
        post = self.get_post(response)
        self.context_test(post)

    def test_group_list_show_correct_context(self):
        response = self.authorized.get(reverse(
            'posts:group_list', kwargs={'slug': self.group.slug}))
        post = self.get_post(response)
        self.context_test(post)
        group = response.context.get('group')
        self.assertEqual(group, self.group)

    def test_profile_page_show_correct_context(self):
        response = self.authorized.get(reverse(
            'posts:profile', kwargs={'username': self.user.username}))
        post = self.get_post(response)
        self.context_test(post)
        user_author = response.context.get('user_author')
        self.assertEqual(user_author, self.user)

    def test_post_detail_page_show_correct_context(self):
        response = self.authorized.get(reverse(
            'posts:post_detail', kwargs={'post_id': self.post.id}))
        context_post = response.context.get('post')
        self.context_test(context_post)
        form = response.context.get('form')
        self.assertIsInstance(form, CommentForm)
        form_field = form.fields.get('text')
        self.assertIsInstance(form_field, forms.fields.CharField)
        comments = response.context.get('comments')
        comment = comments[0]
        self.assertEqual(comment, self.comment)

    def test_post_edit_detail_page_show_correct_context(self):
        response = self.authorized.get(reverse(
            'posts:post_edit', kwargs={'post_id': self.post.pk}))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for value in form_fields.items():
            with self.subTest(value=value):
                form = response.context.get('form')
                self.assertIsInstance(form, PostForm)
                form_fields = form.fields.get(value)
        self.assertIn('is_edit', response.context)
        self.assertTrue(response.context['is_edit'])

    def test_post_create_detail_page_show_correct_context(self):
        response = self.authorized.get(reverse('posts:post_create'))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for value in form_fields.items():
            with self.subTest(value=value):
                form = response.context.get('form')
                self.assertIsInstance(form, PostForm)
                form_fields = form.fields.get(value)

    def test_new_group_posts_has_no_post(self):
        group = Group.objects.create(
            title='Тестовая группа',
            slug='new_test_slug',
            description='Описание группы'
        )
        response = self.authorized.get(reverse(
            'posts:group_list',
            kwargs={'slug': group.slug}))
        page_obj = response.context['page_obj']
        self.assertNotIn(self.post, page_obj)

    def test_cache(self):
        """Проверка работы кэша."""
        post = Post.objects.create(
            author=self.post.author,
            text='Тестовый пост',
            group=self.group,
        )
        response = self.client.get(reverse('posts:index'))
        posts = response.content
        post.delete()
        response_after_del_post = self.client.get(reverse('posts:index'))
        self.assertEqual(posts, response_after_del_post.content)
        cache.clear()
        response_after_clear_cash = self.client.get(reverse('posts:index'))
        self.assertNotEqual(
            response_after_clear_cash.content, response_after_del_post.content
        )


class FollowViewsTest(TestCase):
    def setUp(self):
        cache.clear()

        self.client_auth_follower = Client()
        self.client_auth_following = Client()
        self.user_follower = User.objects.create_user(
            username='First', email='first@mail.ru', password='pass')
        self.user_following = User.objects.create_user(
            username='Second', email='second@mail.ru', password='pass')
        self.post = Post.objects.create(
            author=self.user_following,
            text='test_post'
        )
        self.client_auth_follower.force_login(self.user_follower)
        self.client_auth_following.force_login(self.user_following)

    def test_follow(self):
        Follow.objects.all().delete()
        self.client_auth_follower.get(reverse('posts:profile_follow', kwargs={
            'username': self.user_following.username}))
        follow_exists = Follow.objects.filter(
            user=self.user_follower,
            author=self.user_following
        ).exists()
        self.assertTrue(follow_exists)

    def test_unfollow(self):
        Follow.objects.get_or_create(
            user=self.user_follower,
            author=self.user_following
        )

        self.client_auth_follower.get(reverse(
            'posts:profile_unfollow', kwargs={
                'username': self.user_following.username}))
        follow_not_exists = Follow.objects.filter(
            user=self.user_follower,
            author=self.user_following
        ).exists()
        self.assertFalse(follow_not_exists)


class PaginatorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='author')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
            description='Тестовое описание',
        )

        Post.objects.bulk_create(
            [Post(
                text=f'Пост {i}',
                author=cls.user,
                group=cls.group)
                for i in range(settings.PAGE_SIZE + PAGE_SIZE_2)])

    def setUp(self):
        self.authorized = Client()
        self.authorized.force_login(self.user)
        cache.clear()

    def test_post_paginator(self):
        posts_on_first_page = settings.PAGE_SIZE
        posts_on_second_page = PAGE_SIZE_2
        templates_page_names = [
            reverse('posts:index'),
            reverse('posts:group_list',
                    kwargs={'slug': self.group.slug}),
            reverse('posts:profile',
                    kwargs={'username': self.user.username})
        ]
        for page in templates_page_names:
            with self.subTest(page=page):
                self.assertEqual(len(self.authorized.get(
                    page).context.get('page_obj')),
                    posts_on_first_page)
                self.assertEqual(
                    len(
                        self.authorized.get(f'{page}?page=2').context.get(
                            'page_obj'
                        )
                    ),
                    posts_on_second_page,
                )
