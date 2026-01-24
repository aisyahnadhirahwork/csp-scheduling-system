from django.shortcuts import redirect

def redirect_by_role(user):
    if user.user_type == "doctor":
        return redirect("doctor-dashboard")
    elif user.user_type == "patient":
        return redirect("patient-dashboard")
    return redirect("login")
