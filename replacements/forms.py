# replacements/forms.py
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    
    user_type = forms.ChoiceField(
        choices=[
            ('student', 'Student'),
            ('lecturer', 'Lecturer'),
            ('admin', 'Admin'),
        ],
        required=True,
        widget=forms.RadioSelect
    )
    
    # ID fields
    student_id = forms.CharField(max_length=50, required=False, label="Student ID")
    employee_id = forms.CharField(max_length=50, required=False, label="Employee ID")
    admin_id = forms.CharField(max_length=50, required=False, label="Admin ID")
    
    # Security codes
    lecturer_code = forms.CharField(
        max_length=50, 
        required=False, 
        label="Lecturer Access Code",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    admin_code = forms.CharField(
        max_length=50, 
        required=False, 
        label="Admin Access Code",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        for field_name in self.fields:
            if field_name not in ['lecturer_code', 'admin_code']:  # These already have class
                self.fields[field_name].widget.attrs['class'] = 'form-control'
        self.fields['user_type'].widget.attrs['class'] = 'form-check-input'
    
    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        student_id = cleaned_data.get('student_id')
        employee_id = cleaned_data.get('employee_id')
        admin_id = cleaned_data.get('admin_id')
        lecturer_code = cleaned_data.get('lecturer_code')
        admin_code = cleaned_data.get('admin_code')
        
        if user_type == 'student':
            if not student_id:
                raise forms.ValidationError("Student ID is required for student registration")
        
        elif user_type == 'lecturer':
            if not employee_id:
                raise forms.ValidationError("Employee ID is required for lecturer registration")
            if not lecturer_code:
                raise forms.ValidationError("Lecturer Access Code is required")
            if lecturer_code != settings.LECTURER_SECRET_CODE:
                raise forms.ValidationError("Invalid Lecturer Access Code. Please contact your administrator.")

        elif user_type == 'admin':
            if not admin_id:
                raise forms.ValidationError("Admin ID is required for admin registration")
            if not admin_code:
                raise forms.ValidationError("Admin Access Code is required")
            if admin_code != settings.ADMIN_SECRET_CODE:
                raise forms.ValidationError("Invalid Admin Access Code. Please contact your system administrator.")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super(UserRegistrationForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            
            user_type = self.cleaned_data['user_type']
            
            if user_type == 'student':
                stored_student_id = self.cleaned_data.get('student_id', '')
                stored_employee_id = ''
            elif user_type == 'lecturer':
                stored_student_id = ''
                stored_employee_id = self.cleaned_data.get('employee_id', '')
            else:  # admin
                stored_student_id = ''
                stored_employee_id = self.cleaned_data.get('admin_id', '')
            
            UserProfile.objects.create(
                user=user,
                user_type=user_type,
                student_id=stored_student_id,
                employee_id=stored_employee_id
            )
        
        return user


class UserLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
    )