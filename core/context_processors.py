def navbar_counts(request):
    """
    Safely injects cart_count and wishlist_count into every template context.
    Handles cases where the user is anonymous or the related object doesn't exist yet.
    """
    cart_count = 0
    wishlist_count = 0

    if request.user.is_authenticated:
        try:
            cart_count = request.user.cart.items.count()
        except Exception:
            cart_count = 0

        try:
            wishlist_count = request.user.wishlist.items.count()
        except Exception:
            wishlist_count = 0

    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
    }
