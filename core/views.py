from django.shortcuts import render
from products.models import Product


def home(request):
    signature_products = (
        Product.objects
        .filter(
            is_active=True,
            is_deleted=False,
            is_featured=True
        )
        .select_related('brand', 'category')
        .prefetch_related('variants__images', 'variants')
        .order_by('-created_at')[:3]
    )

    return render(request, 'core/home.html', {
        'signature_products': signature_products
    })