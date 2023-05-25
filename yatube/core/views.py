from django.shortcuts import render


def page_not_found(request, exception):
    return render(request, 'templates/core/404.html', {'path': request.path}, status=404)


def permission_denied(request, exception):
    return render(request, 'templates/core/403.html', status=403)
