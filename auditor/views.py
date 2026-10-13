from django.shortcuts import render

from .services.scanner import (
    scan_website,
)


def home(request):
    return render(
        request,
        "auditor/home.html",
    )


def run_audit(request):

    if request.method != "POST":
        return render(
            request,
            "auditor/partials/audit_result.html",
            {
                "error":
                    "Invalid request."
            },
        )


    url = request.POST.get(
        "url",
        "",
    ).strip()


    if not url:
        return render(
            request,
            "auditor/partials/audit_result.html",
            {
                "error":
                    "Please enter a website URL."
            },
        )


    if not url.startswith(
        (
            "http://",
            "https://",
        )
    ):
        url = (
            "https://"
            + url
        )


    try:

        report = scan_website(
            url
        )

        return render(
            request,
            "auditor/partials/audit_result.html",
            {
                "report":
                    report
            },
        )

    except Exception as e:

        return render(
            request,
            "auditor/partials/audit_result.html",
            {
                "error":
                    str(e)
            },
        )