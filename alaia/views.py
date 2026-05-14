from django.shortcuts import render


def custom_404(request, exception):
    """Custom 404 handler — renders templates/404.html with proper HTTP status."""
    return render(request, '404.html', status=404)
