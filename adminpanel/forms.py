from django import forms
from products.models import Product, ProductVariant, VariantImage, Category, Brand




class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'brand', 'occasions', 'is_active', 'is_featured']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter product name', 'class': 'form-input'}),
            'description': forms.Textarea(attrs={'placeholder': 'Enter product description', 'class': 'form-input', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'brand': forms.Select(attrs={'class': 'form-input'}),
            'occasions': forms.CheckboxSelectMultiple(),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Include active categories plus the currently assigned inactive one
        active_categories = Category.objects.filter(is_active=True, is_deleted=False)
        if self.instance.pk and self.instance.category and not self.instance.category.is_active:
            active_categories = list(active_categories) + [self.instance.category]
        self.fields['category'].queryset = Category.objects.filter(id__in=[c.id for c in active_categories])
        # Same for brands
        active_brands = Brand.objects.filter(is_active=True)
        if self.instance.pk and self.instance.brand and not self.instance.brand.is_active:
            active_brands = list(active_brands) + [self.instance.brand]
        self.fields['brand'].queryset = Brand.objects.filter(id__in=[b.id for b in active_brands])
        self.fields['description'].required = False
        self.fields['occasions'].widget = forms.CheckboxSelectMultiple()

    def clean_category(self):
        cat = self.cleaned_data['category']
        # Allow if the category is active, or if it's the same as the current instance's inactive category
        if cat.is_active:
            return cat
        if self.instance.pk and cat.id == self.instance.category_id:
            return cat
        raise forms.ValidationError('Cannot assign product to inactive category.')

    def clean_brand(self):
        brand = self.cleaned_data['brand']
        # Allow if brand is active, or if it's the same as the current instance's inactive brand
        if brand.is_active:
            return brand
        if self.instance.pk and brand.id == self.instance.brand_id:
            return brand
        raise forms.ValidationError('Cannot assign product to inactive brand.')




class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['color', 'size', 'price', 'sales_price', 'stock']
        widgets = {
            'color': forms.TextInput(attrs={'placeholder': 'e.g. Midnight Blue', 'class': 'form-input'}),
            'size': forms.TextInput(attrs={'placeholder': 'e.g. 42', 'class': 'form-input'}),
            'price': forms.NumberInput(attrs={'placeholder': '0.00', 'class': 'form-input', 'step': '0.01'}),
            'sales_price': forms.NumberInput(attrs={'placeholder': 'Optional', 'class': 'form-input', 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'placeholder': '0', 'class': 'form-input'}),
        }


VariantImageFormSet = forms.inlineformset_factory(
    ProductVariant,
    VariantImage,
    fields=['image'],
    extra=1,
    can_delete=True,
)