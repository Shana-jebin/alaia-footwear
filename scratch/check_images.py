import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alaia.settings')
django.setup()

from products.models import Product, ProductVariant, VariantImage

print(f"{'Product':<40} | {'Variant':<20} | {'Image Path':<50} | {'Exists?'}")
print("-" * 125)

for product in Product.objects.all()[:10]:
    for variant in product.variants.all():
        for img in variant.images.all():
            path = img.image.path if img.image else "None"
            exists = os.path.exists(path) if img.image else False
            print(f"{product.name[:38]:<40} | {variant.color[:18]:<20} | {str(img.image)[:48]:<50} | {exists}")
