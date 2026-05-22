import json
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q
from accounts.models import Address
from products.models import Cart, CartItem, Coupon, Product, ProductVariant
from .models import (
    CouponUsage, Order, OrderItem,
    Wallet, WalletTransaction,
    Wishlist, WishlistItem,
)
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse



def _get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def _wishlist(user):
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return wishlist


def _validate_coupon_for_user(code, user, subtotal):
   
    now = timezone.now()
    try:
        coupon = Coupon.objects.get(
            code__iexact=code,
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now,
        )
    except Coupon.DoesNotExist:
        return None, 0, "Invalid or expired coupon code."

    if subtotal < coupon.min_order:
        return None, 0, f"Minimum order of ₹{coupon.min_order:.0f} required."

    if coupon.discount_type == 'flat' and subtotal <= coupon.discount_value:
        return None, 0, f"Order total must be greater than the discount value (₹{coupon.discount_value:.0f})."

    ok, msg = coupon.can_user_apply(user)
    if not ok:
        return None, 0, msg

    discount = coupon.compute_discount(subtotal)
    return coupon, discount, ''

@login_required
@require_POST
def wallet_add_money(request):
    try:
        data   = json.loads(request.body)
        amount = Decimal(str(data.get('amount', 0)))
    except Exception:
        return JsonResponse({'error': 'Invalid amount.'}, status=400)

    if amount < Decimal('1'):
        return JsonResponse({'error': 'Minimum amount is ₹1.'}, status=400)
    if amount > Decimal('10000'):
        return JsonResponse({'error': 'Maximum amount is ₹10,000.'}, status=400)

    wallet = _get_wallet(request.user)
    wallet.credit(
        amount,
        description=f"Money added to wallet",
    )
    return JsonResponse({
        'success': True,
        'message': f'₹{amount:.0f} added to your wallet.',
        'new_balance': str(wallet.balance),
    })

@login_required
@require_POST
def wallet_razorpay_order(request):
    from decimal import Decimal
    import razorpay

    try:
        amount = Decimal(str(request.POST.get('amount', 0)))
    except:
        messages.error(request, "Invalid amount")
        return redirect('orders:wallet')

    if amount < Decimal('1') or amount > Decimal('10000'):
        messages.error(request, "Invalid amount")
        return redirect('orders:wallet')

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    order = client.order.create({
        "amount": int(amount * 100),
        "currency": "INR",
        "payment_capture": 1,
        "notes": {
            "user_id": str(request.user.id)
        }
    })

    callback_url = request.build_absolute_uri(reverse('orders:wallet_razorpay_callback'))
    if not callback_url.startswith('http://localhost') and not callback_url.startswith('http://127.0.0.1'):
        callback_url = callback_url.replace('http://', 'https://')

    return render(request, 'orders/wallet_payment.html', {
        'amount': amount,
        'amount_paise': order["amount"],
        'razorpay_order_id': order["id"],
        'RAZORPAY_KEY_ID': settings.RAZORPAY_KEY_ID,
        'callback_url': callback_url,
    })

@csrf_exempt
@require_POST
def wallet_razorpay_callback(request):
    
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
    razorpay_order_id   = request.POST.get('razorpay_order_id', '')
    razorpay_signature  = request.POST.get('razorpay_signature', '')
    

  
    if request.POST.get('error[code]') or not razorpay_payment_id:
        messages.error(request, 'Wallet top-up payment failed. Please try again.')
        user_id = None
        if razorpay_order_id:
            try:
                import razorpay
                client = razorpay.Client(
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                )
                rz_order = client.order.fetch(razorpay_order_id)
                notes = rz_order.get('notes') or {}
                user_id = notes.get('user_id')
            except Exception:
                pass
        if user_id:
            from django.core import signing
            token = signing.dumps({'wallet_topup': False, 'user_id': user_id})
            return redirect(f"{reverse('orders:wallet')}?token={token}")
        return redirect('orders:wallet')

    try:
        import razorpay
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        client.utility.verify_payment_signature({
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        })
    except Exception:
        messages.error(request, 'Payment verification failed. Contact support.')
        user_id = None
        if razorpay_order_id:
            try:
                import razorpay
                client = razorpay.Client(
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                )
                rz_order = client.order.fetch(razorpay_order_id)
                notes = rz_order.get('notes') or {}
                user_id = notes.get('user_id')
            except Exception:
                pass
        if user_id:
            from django.core import signing
            token = signing.dumps({'wallet_topup': False, 'user_id': user_id})
            return redirect(f"{reverse('orders:wallet')}?token={token}")
        return redirect('orders:wallet')

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    payment = client.payment.fetch(razorpay_payment_id)

    notes = payment.get("notes") or {}

    if isinstance(notes, list):
        notes = {}
    user_id = notes.get("user_id")

    if not user_id:
        return HttpResponse("Invalid payment data", status=400)

    from django.contrib.auth.models import User

    user = User.objects.get(id=user_id)

    amount = Decimal(payment.get("amount", 0)) / 100

    wallet = _get_wallet(user)
    wallet.credit(
        amount,
        description=f"Wallet top-up via Razorpay ({razorpay_payment_id})",
    )
    messages.success(request, f'₹{amount:.0f} added to your wallet successfully!')
    from django.core import signing
    token = signing.dumps({'wallet_topup': True, 'user_id': user.id})
    return redirect(f"{reverse('orders:wallet')}?token={token}")

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related(
        'variant', 'variant__product', 'variant__product__brand'
    ).prefetch_related('variant__images')

    valid_items   = []
    blocked_names = []
    for item in items:
        v = item.variant
        is_available = (v and not v.is_deleted and v.product.is_active 
                        and not v.product.is_deleted and v.product.category.is_active 
                        and v.product.brand.is_active)
        
        if not is_available:
            blocked_names.append(f"{v.product.name if v else 'Unknown Item'} (Unavailable)")
        elif v.stock <= 0:
            blocked_names.append(f"{v.product.name} (Out of Stock)")
        elif v.stock < item.quantity:
            blocked_names.append(f"{v.product.name} (Insufficient Stock: only {v.stock} left)")
        else:
            valid_items.append(item)

    if not valid_items:
        messages.error(request, "Your cart has no available items to checkout.")
        return redirect('orders:cart')

    if blocked_names:
        messages.warning(request, f"Removed unavailable items: {', '.join(blocked_names)}")

    from decimal import Decimal

    subtotal = sum(
    (Decimal(str(item.variant.final_price)) * item.quantity for item in valid_items),
    Decimal("0.00")
)

    shipping = Decimal("0") if subtotal >= Decimal("2999") else Decimal("99")
    total    = subtotal + shipping

    addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created_at')
    if addresses.count() < 1:
        messages.error(request, "Please add at least one delivery address before checkout.")
        return redirect(f"{reverse('address_list')}?next={request.path}")
    default_address = addresses.filter(is_default=True).first() or addresses.first()

    wallet  = _get_wallet(request.user)

   
    now         = timezone.now()
    product_ids = [i.variant.product_id for i in valid_items]
    category_ids= [i.variant.product.category_id for i in valid_items]
    coupons     = Coupon.objects.filter(
        is_active=True, valid_from__lte=now, valid_to__gte=now,
        min_order__lte=subtotal,
    ).filter(
        Q(products__id__in=product_ids) | Q(categories__id__in=category_ids)
        | Q(products__isnull=True, categories__isnull=True)
    ).distinct()

    return render(request, 'orders/checkout.html', {
        'items':           valid_items,
        'addresses':       addresses,
        'default_address': default_address,
        'subtotal':        subtotal,
        'shipping':        shipping,
        'total':           total,
        'coupons':         coupons,
        'wallet':          wallet,
        'RAZORPAY_KEY_ID': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    })




@login_required
def apply_coupon(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method.'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    code     = data.get('code', '').strip().upper()
    subtotal = Decimal(str(data.get('subtotal', 0)))

    if not code:
        return JsonResponse({'error': 'Please enter a coupon code.'}, status=400)

    coupon, discount, err = _validate_coupon_for_user(code, request.user, subtotal)
    if err:
        return JsonResponse({'error': err}, status=400)

    return JsonResponse({
        'success':  True,
        'discount': discount,
        'code':     coupon.code,
        'message':  f'Coupon applied! You saved ₹{discount:.0f}',
    })


@login_required
@transaction.atomic
def place_order(request):
    if request.method != 'POST':
        return redirect('orders:checkout')

    from decimal import Decimal

    cart  = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related(
        'variant', 'variant__product', 'variant__product__brand'
    ).prefetch_related('variant__images')

    import json

    if 'application/json' in request.content_type:
        data = json.loads(request.body)
        address_id     = data.get('address_id')
        payment_method = data.get('payment_method')
        coupon_code    = data.get('coupon_code', '').strip().upper()
    else:
        address_id     = request.POST.get('address_id')
        payment_method = request.POST.get('payment_method')
        coupon_code    = request.POST.get('coupon_code', '').strip().upper()

    # safety checks
    if not address_id:
        messages.error(request, "Please select a delivery address.")
        return redirect('orders:checkout')

    if not payment_method:
        messages.error(request, "Please select a payment method.")
        return redirect('orders:checkout')

    address = get_object_or_404(Address, id=address_id, user=request.user)

    valid_items = []
    for item in items:
        v = item.variant
        is_available = (v and not v.is_deleted and v.product.is_active
                        and not v.product.is_deleted and v.product.category.is_active
                        and v.product.brand.is_active)

        if not is_available:
            messages.error(request, f"'{v.product.name if v else 'Item'}' is no longer available.")
            return redirect('orders:cart')
        elif v.stock < item.quantity:
            messages.error(request, f"'{v.product.name}' has insufficient stock (only {v.stock} left).")
            return redirect('orders:cart')
        else:
            valid_items.append(item)

    if not valid_items:
        messages.error(request, "No valid items to order.")
        return redirect('orders:cart')

    subtotal = sum(
        (Decimal(str(item.variant.final_price)) * item.quantity for item in valid_items),
        Decimal("0.00")
    )

    shipping = Decimal('0') if subtotal >= Decimal('2999') else Decimal('99')
    discount = Decimal('0')
    coupon   = None

    if coupon_code:
        coupon, disc_float, err = _validate_coupon_for_user(coupon_code, request.user, subtotal)
        if coupon:
            discount = Decimal(str(disc_float))

    total = subtotal + shipping - discount

    if payment_method == "cod" and total > 2500:
        messages.error(request, "COD is not available for orders above ₹2500.")
        return redirect('orders:checkout')

    if payment_method == 'wallet':
        wallet = _get_wallet(request.user)
        if wallet.balance < total:
            messages.error(request, f"Insufficient wallet balance. Your balance: ₹{wallet.balance:.0f}")
            return redirect('orders:checkout')

    # ── Create the order (stock deducted after payment for online) ──
    order = Order.objects.create(
        user=request.user,
        full_name=address.full_name,
        address_line1=address.address_line1,
        address_line2=address.address_line2 or '',
        city=address.city,
        state=address.state,
        postal_code=address.postal_code,
        country=address.country,
        phone=address.phone,
        payment_method=payment_method,
        subtotal=subtotal,
        discount=discount,
        shipping=shipping,
        total=total,
        coupon_code=coupon_code,
        payment_status='paid' if payment_method in ('wallet',) else 'pending',
    )

    for item in valid_items:
        v   = item.variant
        # Try this variant's image first, then any other variant image for the same product
        img = v.images.first()
        if img and img.image:
            image_url = img.image.url
        else:
            fallback = v.product.variants.exclude(pk=v.pk).filter(images__isnull=False).first()
            fallback_img = fallback.images.first() if fallback else None
            image_url = fallback_img.image.url if (fallback_img and fallback_img.image) else ''

        OrderItem.objects.create(
            order=order,
            variant=v,
            product_name=v.product.name,
            brand_name=v.product.brand.name,
            color=v.color,
            size=v.size,
            image_url=image_url,
            quantity=item.quantity,
            unit_price=v.final_price,
        )

    # ── Online payment: redirect to Razorpay embedded checkout ──
    if payment_method == 'online':
        # Stock and cart cleared only AFTER payment confirmed in razorpay_callback
        return redirect('orders:razorpay_payment', order_id=order.order_id)

    # ── COD / Wallet: deduct stock and clear cart immediately ──
    for item in valid_items:
        v = item.variant
        v.stock -= item.quantity
        v.save(update_fields=['stock'])

    if payment_method == 'wallet':
        wallet = _get_wallet(request.user)
        wallet.debit(
            total,
            description=f"Payment for order {order.order_id}",
            order=order,
        )

    if coupon:
        CouponUsage.objects.create(coupon=coupon, user=request.user, order=order)
        coupon.used_count += 1
        coupon.save(update_fields=['used_count'])

    cart.items.all().delete()

    return redirect('orders:order_success', order_id=order.order_id)

@login_required
def razorpay_payment(request, order_id):
    """Show the Razorpay payment page."""
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    if order.payment_status == 'paid':
        return redirect('orders:order_success', order_id=order.order_id)

    try:
        import razorpay
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        rz_order = client.order.create({
        'amount': int(float(order.total) * 100),
        'currency': 'INR',
        'receipt': order.order_id,
        'payment_capture': 1,
        'notes': {
            'user_id': str(request.user.id)
        }
})
        
        print("RAZORPAY ORDER CREATED:", rz_order)


        order.razorpay_order_id = rz_order['id']
        order.save(update_fields=['razorpay_order_id'])
    except Exception as e:
        messages.error(request, f"Payment gateway error: {e}")
        return redirect('orders:payment_failed', order_id=order.order_id)

    return render(request, 'orders/razorpay_payment.html', {
        'order':           order,
        'RAZORPAY_KEY_ID': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': order.razorpay_order_id,
        'amount_paise':      int(float(order.total) * 100),
    })
@csrf_exempt
@require_POST
def razorpay_callback(request):
    import logging
    logger = logging.getLogger(__name__)
    logger.info("=== RAZORPAY CALLBACK ===")

    data = request.POST
    logger.info("CALLBACK DATA: %s", dict(data))

    razorpay_payment_id = data.get('razorpay_payment_id', '')
    razorpay_order_id   = data.get('razorpay_order_id', '')
    razorpay_signature  = data.get('razorpay_signature', '')

    # ── Helper: find the order from any available field ──
    def _find_order_from_error():
        """Try every possible field Razorpay might send on error."""
        # 1. Parse error[metadata] as a JSON string if present (Razorpay sends it as a JSON string)
        rz_metadata_str = data.get('error[metadata]', '')
        if rz_metadata_str:
            try:
                import json
                metadata = json.loads(rz_metadata_str)
                rz_oid = metadata.get('order_id', '')
                if rz_oid:
                    return Order.objects.get(razorpay_order_id=rz_oid)
            except Exception:
                pass

        # 2. error[metadata][order_id]  — fallback
        rz_oid = data.get('error[metadata][order_id]', '')
        if rz_oid:
            try:
                return Order.objects.get(razorpay_order_id=rz_oid)
            except Order.DoesNotExist:
                pass

        # 3. Top-level razorpay_order_id (some failure modes still send it)
        if razorpay_order_id:
            try:
                return Order.objects.get(razorpay_order_id=razorpay_order_id)
            except Order.DoesNotExist:
                pass

        # 4. error[metadata][payment_id] — fetch order via Razorpay API
        rz_pid = data.get('error[metadata][payment_id]', '')
        if not rz_pid and rz_metadata_str:
            try:
                import json
                metadata = json.loads(rz_metadata_str)
                rz_pid = metadata.get('payment_id', '')
            except Exception:
                pass
        if rz_pid:
            try:
                import razorpay
                client = razorpay.Client(
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                )
                payment = client.payment.fetch(rz_pid)
                rz_oid = payment.get('order_id', '')
                if rz_oid:
                    return Order.objects.get(razorpay_order_id=rz_oid)
            except Exception:
                pass

        return None

    # ── Payment failed / cancelled by Razorpay ──
    if data.get('error[code]') or data.get('error[description]'):
        error_desc = data.get('error[description]', 'Payment failed')
        logger.warning("Razorpay error callback: %s", error_desc)

        order = _find_order_from_error()
        if order:
            order.payment_status = 'failed'
            order.save(update_fields=['payment_status', 'updated_at'])
            from django.contrib import messages as msg_framework
            msg_framework.error(request, f'Payment failed: {error_desc}')
            from django.core import signing
            token = signing.dumps({'order_id': order.order_id, 'user_id': order.user.id})
            return redirect(f"{reverse('orders:payment_failed', kwargs={'order_id': order.order_id})}?token={token}")

        # Could not find the order at all — go to order list
        logger.error("Razorpay error callback: could not find order. Data: %s", dict(data))
        return redirect('orders:order_list')

    # ── No order ID at all ──
    if not razorpay_order_id:
        return redirect('orders:order_list')

    try:
        order = Order.objects.get(razorpay_order_id=razorpay_order_id)
    except Order.DoesNotExist:
        return redirect('orders:order_list')

    # ── Missing payment ID or signature ──
    if not razorpay_payment_id or not razorpay_signature:
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status', 'updated_at'])
        from django.core import signing
        token = signing.dumps({'order_id': order.order_id, 'user_id': order.user.id})
        return redirect(f"{reverse('orders:payment_failed', kwargs={'order_id': order.order_id})}?token={token}")

    # ── Verify signature and complete the order ──
    try:
        import razorpay
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        client.utility.verify_payment_signature({
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        })

        # ── Payment verified: deduct stock, clear cart, mark paid ──
        with transaction.atomic():
            order.razorpay_payment_id = razorpay_payment_id
            order.payment_status      = 'paid'
            order.status              = 'confirmed'
            order.save(update_fields=['razorpay_payment_id', 'payment_status', 'status', 'updated_at'])

            # Deduct stock for each order item
            for item in order.items.select_related('variant').all():
                if item.variant:
                    item.variant.stock -= item.quantity
                    item.variant.save(update_fields=['stock'])

            # Clear user's cart
            try:
                cart = Cart.objects.get(user=order.user)
                cart.items.all().delete()
            except Cart.DoesNotExist:
                pass

            # Apply coupon usage if a coupon was used and not already recorded
            if order.coupon_code:
                from products.models import Coupon
                try:
                    coupon = Coupon.objects.get(code__iexact=order.coupon_code)
                    if not CouponUsage.objects.filter(coupon=coupon, order=order).exists():
                        CouponUsage.objects.create(coupon=coupon, user=order.user, order=order)
                        coupon.used_count += 1
                        coupon.save(update_fields=['used_count'])
                except Coupon.DoesNotExist:
                    pass

        from django.core import signing
        token = signing.dumps({'order_id': order.order_id, 'user_id': order.user.id})
        return redirect(f"{reverse('orders:order_success', kwargs={'order_id': order.order_id})}?token={token}")

    except Exception as e:
        logger.error("Razorpay signature verification failed: %s", str(e))
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status', 'updated_at'])
        from django.core import signing
        token = signing.dumps({'order_id': order.order_id, 'user_id': order.user.id})
        return redirect(f"{reverse('orders:payment_failed', kwargs={'order_id': order.order_id})}?token={token}")

def payment_failed(request, order_id):
    """Payment failure page with retry option."""
    token = request.GET.get('token')
    if token:
        from django.core import signing
        try:
            data = signing.loads(token, max_age=300)
            if data.get('order_id') == order_id:
                from django.contrib.auth import login
                from django.contrib.auth.models import User
                user = User.objects.get(id=data['user_id'])
                login(request, user)
        except Exception:
            pass

    if not request.user.is_authenticated:
        return redirect(f"{reverse('account_login')}?next={request.path}")

    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'orders/payment_failed.html', {'order': order})


@login_required
@require_POST
def retry_payment(request, order_id):
    """Re-initiate Razorpay payment for a failed order."""
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if order.payment_status == 'paid':
        return redirect('orders:order_success', order_id=order.order_id)
    from django.http import JsonResponse
    import razorpay

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    payment = client.order.create({
        "amount": int(total * 100),
        "currency": "INR",
        "payment_capture": 1
    })

    order.razorpay_order_id = payment['id']
    order.save()

    return JsonResponse({
        "key": settings.RAZORPAY_KEY_ID,
        "amount": payment['amount'],
        "order_id": payment['id'],
        "success_url": f"/orders/success/{order.order_id}/"
    })




def order_success(request, order_id):
    token = request.GET.get('token')
    if token:
        from django.core import signing
        try:
            data = signing.loads(token, max_age=300)
            if data.get('order_id') == order_id:
                from django.contrib.auth import login
                from django.contrib.auth.models import User
                user = User.objects.get(id=data['user_id'])
                login(request, user)
        except Exception:
            pass

    if not request.user.is_authenticated:
        return redirect(f"{reverse('account_login')}?next={request.path}")

    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    # Safety net: ensure cart is cleared after a successful order
    if order.payment_status == 'paid' or order.payment_method == 'cod':
        try:
            cart = Cart.objects.get(user=request.user)
            cart.items.all().delete()
        except Cart.DoesNotExist:
            pass

    return render(request, 'orders/order-success.html', {'order': order})




@login_required
def order_list(request):
    # Hide online orders that are still pending or failed to keep history clean
    orders = Order.objects.filter(user=request.user).exclude(
        payment_method='online',
        payment_status__in=['pending', 'failed']
    )
    q = request.GET.get('q', '').strip()
    if q:
        orders = orders.filter(
            Q(order_id__icontains=q) | Q(items__product_name__icontains=q)
        ).distinct()
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    return render(request, 'orders/order-list.html', {
        'orders':         orders.order_by('-created_at'),
        'q':              q,
        'status_filter':  status_filter,
        'status_choices': Order.STATUS_CHOICES,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'orders/order-detail.html', {'order': order})



@login_required
@require_POST
@transaction.atomic
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if not order.can_cancel:
        return JsonResponse({'error': 'This order cannot be cancelled.'}, status=400)

    try:
        data   = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = ''

    for item in order.items.filter(status='active'):
        if item.variant:
            item.variant.stock += item.quantity
            item.variant.save(update_fields=['stock'])
        item.status        = 'cancelled'
        item.cancel_reason = reason
        item.cancelled_at  = timezone.now()
        item.save()

    # Refund logic
    refund_amount = Decimal('0')
    if order.payment_status == 'paid':
        refund_amount = Decimal(str(order.refund_amount()))

    # Cancel order
    order.status   = 'cancelled'
    if refund_amount > 0:
        order.payment_status = 'refunded'
    order.save(update_fields=['status', 'payment_status', 'updated_at'])

   
    if refund_amount > 0:
        wallet = _get_wallet(request.user)
        wallet.credit(
            refund_amount,
            description=f"Refund for cancelled order {order.order_id}",
            order=order,
        )
        return JsonResponse({
            'success':       True,
            'message':       f'Order cancelled. ₹{refund_amount:.0f} refunded to your wallet.',
            'refunded':      True,
            'refund_amount': refund_amount,
        })

    return JsonResponse({'success': True, 'message': 'Order cancelled successfully.', 'refunded': False})


@login_required
@require_POST
@transaction.atomic
def cancel_item(request, order_id, item_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    item  = get_object_or_404(OrderItem, id=item_id, order=order)

    if not order.can_cancel or item.status != 'active':
        return JsonResponse({'error': 'This item cannot be cancelled.'}, status=400)

    try:
        data   = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = ''

    if item.variant:
        item.variant.stock += item.quantity
        item.variant.save(update_fields=['stock'])

    item.status        = 'cancelled'
    item.cancel_reason = reason
    item.cancelled_at  = timezone.now()
    item.save()

    # Calculate what was owed BEFORE this cancellation
    active_before = list(order.items.filter(status__in=['active', 'cancelled']))
    # Wait, the item itself just got its status set to 'cancelled' on line 861!
    # So we must compute the 'old' values by treating this item as active.
    active_now = order.items.filter(status='active')
    
    old_subtotal = sum(i.unit_price * i.quantity for i in active_now) + (item.unit_price * item.quantity)
    old_shipping = Decimal('0') if old_subtotal >= Decimal('2999') else Decimal('99')
    old_total    = old_subtotal + old_shipping - order.discount
    
    if not active_now.exists():
        actual_new_total = Decimal('0')
        order.status = 'cancelled'
        # Restore original amounts for history
        all_items = order.items.all()
        new_subtotal = sum(i.unit_price * i.quantity for i in all_items)
        new_shipping = Decimal('0') if new_subtotal >= Decimal('2999') else Decimal('99')
        new_discount = order.discount
        new_total    = new_subtotal + new_shipping - new_discount
    else:
        new_subtotal = sum(i.unit_price * i.quantity for i in active_now)
        new_discount = order.discount
        new_shipping = Decimal('0') if new_subtotal >= Decimal('2999') else Decimal('99')
        new_total    = new_subtotal + new_shipping - new_discount
        actual_new_total = new_total

    order.subtotal = new_subtotal
    order.shipping = new_shipping
    order.total    = new_total
    order.save(update_fields=['status', 'subtotal', 'shipping', 'total', 'updated_at'])

    refund_amount = 0
    if order.payment_method in ('online', 'wallet'):
        refund_amount = float(old_total - actual_new_total)
        if refund_amount > 0:
            wallet = _get_wallet(request.user)
            wallet.credit(
                refund_amount,
                description=f"Refund for cancelled item '{item.product_name}' in order {order.order_id}",
                order=order,
            )

    return JsonResponse({
        'success':       True,
        'message':       'Item cancelled successfully.',
        'refunded':      refund_amount > 0,
        'refund_amount': refund_amount,
        'new_subtotal':  float(new_subtotal),
        'new_total':     float(new_total),
        'new_shipping':  float(new_shipping),
    })
# ── RETURN ORDER ──────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def return_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if not order.can_return:
        return JsonResponse({'error': 'This order is not eligible for return.'}, status=400)

    try:
        data   = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = request.POST.get('reason', '').strip()

    if not reason:
        return JsonResponse({'error': 'A reason is required for returns.'}, status=400)

    for item in order.items.filter(status='active'):
        item.status        = 'return_requested'
        item.return_reason = reason
        item.save()

    order.status = 'return_requested'
    order.save(update_fields=['status', 'updated_at'])

    return JsonResponse({'success': True, 'message': 'Return request submitted. We will process it shortly.'})

@login_required
@require_POST
@transaction.atomic
def return_item(request, order_id, item_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    item  = get_object_or_404(OrderItem, id=item_id, order=order)

    if order.status != 'delivered' or item.status != 'active':
        return JsonResponse({'error': 'This item is not eligible for return.'}, status=400)

    try:
        data   = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = ''

    if not reason:
        return JsonResponse({'error': 'Please provide a reason for return.'}, status=400)

    item.status        = 'return_requested'
    item.return_reason = reason
    item.save()

    if not order.items.filter(status='active').exists():
        order.status = 'return_requested'
        order.save(update_fields=['status', 'updated_at'])

    return JsonResponse({
        'success': True,
        'message': 'Return request submitted for this item.'
    })
# ── WALLET PAGE ───────────────────────────────────────────────────

from django.core.paginator import Paginator

def wallet_page(request):
    token = request.GET.get('token')
    if token:
        from django.core import signing
        try:
            data = signing.loads(token, max_age=300)
            if 'wallet_topup' in data:
                from django.contrib.auth import login
                from django.contrib.auth.models import User
                user = User.objects.get(id=data['user_id'])
                login(request, user)
        except Exception:
            pass

    if not request.user.is_authenticated:
        return redirect(f"{reverse('account_login')}?next={request.path}")

    wallet       = _get_wallet(request.user)
    transaction_list = wallet.transactions.select_related('order').all()
    
    paginator = Paginator(transaction_list, 10)
    page_number = request.GET.get('page')
    transactions = paginator.get_page(page_number)
    
    return render(request, 'orders/wallet.html', {
        'wallet':       wallet,
        'transactions': transactions,
    })


# ── INVOICE DOWNLOAD ──────────────────────────────────────────────

@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    try:
        from io import BytesIO
        from reportlab.lib              import colors
        from reportlab.lib.pagesizes    import A4
        from reportlab.lib.styles       import ParagraphStyle
        from reportlab.lib.units        import mm
        from reportlab.platypus         import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        )

        buffer = BytesIO()
        doc    = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=20*mm, leftMargin=20*mm,
            topMargin=20*mm,   bottomMargin=20*mm
        )

        brand_style = ParagraphStyle('Brand', fontSize=28, fontName='Helvetica-Bold',
                                     textColor=colors.HexColor('#2a2520'), spaceAfter=2)
        sub_style   = ParagraphStyle('Sub', fontSize=9, fontName='Helvetica',
                                     textColor=colors.HexColor('#888888'), spaceAfter=4)
        h2_style    = ParagraphStyle('H2', fontSize=11, fontName='Helvetica-Bold',
                                     textColor=colors.HexColor('#2a2520'), spaceBefore=8, spaceAfter=4)
        body_style  = ParagraphStyle('Body', fontSize=9, fontName='Helvetica',
                                     textColor=colors.HexColor('#333333'), spaceAfter=2)
        small_style = ParagraphStyle('Small', fontSize=8, fontName='Helvetica',
                                     textColor=colors.HexColor('#888888'), spaceAfter=2)

        story = []
        story.append(Paragraph('ALAIA', brand_style))
        story.append(Paragraph('Architectural Footwear · Premium Collection', sub_style))
        story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#c9a96e'), spaceAfter=8))
        story.append(Paragraph('TAX INVOICE', h2_style))

        info_data  = [
            ['Order ID', order.order_id, 'Date', order.created_at.strftime('%d %b %Y')],
            ['Payment',  order.get_payment_method_display(), 'Status', order.get_status_display()],
        ]
        info_table = Table(info_data, colWidths=[35*mm, 65*mm, 25*mm, 45*mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME',     (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME',     (0,0), (0,-1),  'Helvetica-Bold'),
            ('FONTNAME',     (2,0), (2,-1),  'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 9),
            ('TEXTCOLOR',    (0,0), (0,-1),  colors.HexColor('#888888')),
            ('TEXTCOLOR',    (2,0), (2,-1),  colors.HexColor('#888888')),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 8*mm))

        story.append(Paragraph('Ship To', h2_style))
        story.append(Paragraph(order.full_name, body_style))
        story.append(Paragraph(order.address_line1, body_style))
        if order.address_line2:
            story.append(Paragraph(order.address_line2, body_style))
        story.append(Paragraph(f"{order.city}, {order.state} — {order.postal_code}", body_style))
        story.append(Paragraph(order.country, body_style))
        story.append(Paragraph(f"Phone: {order.phone}", body_style))
        story.append(Spacer(1, 6*mm))

        story.append(Paragraph('Order Items', h2_style))
        rows = [['Product', 'Colour / Size', 'Qty', 'Unit Price', 'Subtotal']]
        for item in order.items.exclude(status='cancelled'):
            rows.append([
                item.product_name,
                f"{item.color.title()} / {item.size}",
                str(item.quantity),
                f"₹{item.unit_price:,.0f}",
                f"₹{item.subtotal():,.0f}",
            ])

        item_table = Table(rows, colWidths=[70*mm, 35*mm, 15*mm, 25*mm, 25*mm])
        item_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), colors.HexColor('#2a2520')),
            ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME',      (0,1), (-1,-1),'Helvetica'),
            ('FONTSIZE',      (0,0), (-1,-1), 9),
            ('ALIGN',         (2,0), (-1,-1), 'RIGHT'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#fdfcfa')]),
            ('GRID',          (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
        ]))
        story.append(item_table)
        story.append(Spacer(1, 6*mm))

       
        if order.status == 'cancelled':
            display_subtotal = 0
            display_shipping = 0
            display_total = 0
        else:
            display_subtotal = order.subtotal
            display_shipping = order.shipping
            display_total = order.total

        total_data = [['', 'Subtotal', f"₹{display_subtotal:,.0f}"]]

       
        if float(order.discount) > 0:
            total_data.append(['', f'Discount ({order.coupon_code})', f"- ₹{order.discount:,.0f}"])

       
        total_data.append([
            '',
            'Shipping',
            f"₹{display_shipping:,.0f}" if float(display_shipping) > 0 else 'FREE'
        ])

       
        total_data.append(['', 'TOTAL', f"₹{display_total:,.0f}"])

        tot_table = Table(total_data, colWidths=[100*mm, 40*mm, 30*mm])
        tot_table.setStyle(TableStyle([
            ('FONTNAME',  (1,-1),  (-1,-1), 'Helvetica-Bold'),
            ('FONTNAME',  (0,0),   (-1,-2), 'Helvetica'),
            ('FONTSIZE',  (0,0),   (-1,-1), 9),
            ('ALIGN',     (2,0),   (2,-1),  'RIGHT'),
            ('ALIGN',     (1,0),   (1,-1),  'RIGHT'),
            ('LINEABOVE', (1,-1),  (-1,-1), 1, colors.HexColor('#c9a96e')),
            ('TEXTCOLOR', (1,-1),  (-1,-1), colors.HexColor('#2a2520')),
            ('TOPPADDING',(0,-1),  (-1,-1), 6),
            ('FONTSIZE',  (1,-1),  (-1,-1), 11),
        ]))
        story.append(tot_table)
        story.append(Spacer(1, 10*mm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#dddddd')))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(
            'Thank you for choosing ALAIA. For returns or queries, contact support@alaia.com',
            small_style
        ))

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="ALAIA-Invoice-{order.order_id}.pdf"'
        )
        return response

    except ImportError:
        return HttpResponse(
            f"PDF generation requires reportlab.\npip install reportlab\n\nOrder: {order.order_id}",
            content_type='text/plain'
        )


# ── WISHLIST ──────────────────────────────────────────────────────

@login_required
def wishlist_page(request):
    wishlist = _wishlist(request.user)
    items    = wishlist.items.select_related(
        'product', 'product__brand', 'product__category'
    ).prefetch_related('product__variants__images')

    in_cart = set()
    try:
        in_cart = set(request.user.cart.items.values_list('variant__product_id', flat=True))
    except Exception:
        pass

    return render(request, 'orders/wishlist.html', {
        'wishlist': wishlist,
        'items':    items,
        'in_cart':  in_cart,
    })


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    product  = get_object_or_404(Product, id=product_id, is_active=True, is_deleted=False)
    wishlist = _wishlist(request.user)

    cart = Cart.objects.filter(user=request.user).first()
    if cart and cart.items.filter(variant__product=product).exists():
        return JsonResponse({'success': False, 'message': 'Product already in cart.'})

    item = WishlistItem.objects.filter(wishlist=wishlist, product=product).first()
    if item:
        item.delete()
        added = False
    else:
        WishlistItem.objects.create(wishlist=wishlist, product=product)
        added = True

    return JsonResponse({
        'success': True,
        'added':   added,
        'count':   wishlist.items.count(),
        'message': 'Saved to wishlist' if added else 'Removed from wishlist',
    })


@login_required
def wishlist_status(request):
    wishlist = _wishlist(request.user)
    ids      = list(wishlist.items.values_list('product_id', flat=True))
    return JsonResponse({'product_ids': ids, 'count': len(ids)})


@login_required
@require_POST
def move_to_cart(request, product_id):
    product  = get_object_or_404(Product, id=product_id, is_active=True, is_deleted=False)
    wishlist = _wishlist(request.user)

    variant = product.variants.filter(is_deleted=False, stock__gt=0).order_by('price').first()
    if not variant:
        return JsonResponse({'error': 'No stock available for this product.'}, status=400)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, variant=variant,
        defaults={'quantity': 1, 'price_at_added': variant.final_price}
    )
    if not created:
        if cart_item.quantity + 1 > variant.stock:
            return JsonResponse({'error': 'Not enough stock.'}, status=400)
        cart_item.quantity      += 1
        cart_item.price_at_added = variant.final_price
        cart_item.save()

    WishlistItem.objects.filter(wishlist=wishlist, product=product).delete()

    return JsonResponse({
        'success':    True,
        'message':    'Moved to cart.',
        'cart_count': cart.items.count(),
        'wish_count': wishlist.items.count(),
    })


@login_required
@require_POST
def remove_from_wishlist(request, product_id):
    wishlist = _wishlist(request.user)
    WishlistItem.objects.filter(wishlist=wishlist, product_id=product_id).delete()
    return JsonResponse({'success': True, 'count': wishlist.items.count()})


# ── CART ──────────────────────────────────────────────────────────

@require_POST
def add_to_cart(request, variant_id):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "login required"})

    variant = get_object_or_404(ProductVariant, id=variant_id, is_deleted=False)
    if variant.stock <= 0:
        return JsonResponse({"success": False, "error": "out of stock"})

    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={"quantity": 1, "price_at_added": variant.final_price}
    )
    if not created:
        if cart_item.quantity + 1 > variant.stock:
            return JsonResponse({"success": False, "error": "not enough stock"})
        cart_item.quantity += 1
        cart_item.save()

    WishlistItem.objects.filter(
        wishlist__user=request.user, product=variant.product
    ).delete()

    return JsonResponse({"success": True, "count": cart.items.count()})


def cart_view(request):
    if not request.user.is_authenticated:
        return redirect("account_login")

    cart, _ = Cart.objects.get_or_create(user=request.user)
    items   = cart.items.select_related(
        "variant", "variant__product", "variant__product__brand"
    ).prefetch_related("variant__images")

    total = sum(item.subtotal() for item in items)
    return render(request, "orders/cart.html", {"cart": cart, "items": items, "total": total})
@login_required
def update_cart_quantity(request, item_id, action):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    variant = cart_item.variant

    if action == "increase":
        if cart_item.quantity + 1 > variant.stock:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Not enough stock.'})
            messages.error(request, "Not enough stock available.")
        else:
            cart_item.quantity += 1
            cart_item.save()
    elif action == "decrease":
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    elif action == "remove":
        cart_item.delete()


    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Refresh cart total
        cart = Cart.objects.get(user=request.user)
        items = cart.items.all()
        subtotal = sum(item.subtotal() for item in items)
        subtotal_dec = Decimal(str(subtotal))
        shipping = Decimal('0') if subtotal_dec >= Decimal('2999') else Decimal('99')
        total    = subtotal_dec + shipping
        
        return JsonResponse({
            'success':  True,
            'item_sub': float(cart_item.subtotal()) if cart_item.id else 0,
            'subtotal': float(subtotal),
            'shipping': 'Free' if shipping == 0 else f"₹{shipping:.0f}",
            'total':    float(total),
            'count':    items.count(),
            'item_removed': not CartItem.objects.filter(id=item_id).exists()
        })

    return redirect("orders:cart")