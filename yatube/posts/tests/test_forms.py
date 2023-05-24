from django.test import Client, TestCase
from django.urls import reverse

from ..models import Post, Group, User, Comment


class PostFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание'
        )
        cls.group1 = Group.objects.create(
            title='Изменяем текст',
            slug='test-slug1',
            description='Тестовое описание1'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
            group=cls.group
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_create_post(self):
        test_posts = set(Post.objects.all())
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.id
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, reverse('posts:profile', kwargs={'username': self.user})
        )
        created_post = set(Post.objects.all()) - test_posts
        self.assertEqual(len(created_post), 1)
        post = created_post.pop()
        self.assertEqual(post.text, form_data['text'])
        self.assertEqual(post.group.id, form_data['group'])

    def test_post_edit(self):
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Изменяем текст',
            'group': self.group1.id
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit', kwargs=({'post_id': self.post.id})),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, reverse(
                'posts:post_detail', kwargs={'post_id': self.post.id}
            )
        )
        self.assertEqual(Post.objects.count(), posts_count)
        post_obj = Post.objects.get(id=self.post.id)
        self.assertEqual(post_obj.text, form_data['text'])
        self.assertEqual(post_obj.group.id, form_data['group'])

    def test_guest_cannot_create(self):
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый пост',
            'group': self.group.id
        }
        response = self.guest_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, '/auth/login/?next=/create/'
        )
        self.assertEqual(Post.objects.count(), posts_count)

    def test_create_comment(self):
        """Авториз. пользователь создает комментарий с нужными атрибутами."""
        all_comments = set(Comment.objects.all())
        form_data = {
            'text': 'Комментарий тестовый',
        }
        self.authorized_client.post(
            reverse('posts:add_comment', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        one_more_comment = set(Comment.objects.all())
        comment_set = one_more_comment - all_comments
        comment_count = len(comment_set)
        comment = comment_set.pop()
        self.assertEqual(comment_count, 1)
        self.assertEqual(self.user, comment.author)
        self.assertEqual(form_data['text'], comment.text)
        self.assertEqual(self.post, comment.post)
