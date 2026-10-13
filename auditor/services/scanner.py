from collections import Counter, defaultdict
from math import sqrt

from playwright.sync_api import sync_playwright


# =========================================================
# HELPERS
# =========================================================

def mode_value(items, key):
    values = [
        item.get(key)
        for item in items
        if item.get(key) not in (None, "", "normal", "none")
    ]

    if not values:
        return None

    return Counter(values).most_common(1)[0][0]


def parse_px(value):
    if not value:
        return None

    try:
        return float(str(value).replace("px", "").strip())
    except (TypeError, ValueError):
        return None


def normalize_text(value):
    if not value:
        return ""

    return " ".join(str(value).split()).strip()


def score_from_issues(total, issue_count):
    if not total:
        return 100

    ratio = issue_count / total

    return max(
        0,
        round(100 - (ratio * 100))
    )


def get_severity(field, actual, expected):
    """
    Simple V3 severity rules.
    Later we can make this much smarter.
    """

    if field in [
        "font_size",
        "padding_top",
        "padding_bottom",
        "height",
    ]:
        actual_px = parse_px(actual)
        expected_px = parse_px(expected)

        if actual_px is not None and expected_px is not None:
            difference = abs(actual_px - expected_px)

            if difference >= 24:
                return "major"

            if difference >= 10:
                return "moderate"

            return "minor"

    if field in [
        "background_color",
        "color",
    ]:
        return "moderate"

    if field in [
        "border_radius",
        "font_weight",
        "line_height",
    ]:
        return "minor"

    return "minor"


def build_issue(
    item,
    group_name,
    field,
    actual,
    expected,
):
    return {
        "group": group_name,
        "text": (
            normalize_text(item.get("text"))
            or item.get("tag")
            or "Unnamed element"
        ),
        "tag": item.get("tag"),
        "field": field,
        "actual": actual,
        "expected": expected,
        "severity": get_severity(
            field,
            actual,
            expected,
        ),
    }


def build_group_report(
    name,
    items,
    fields,
    category,
):
    if not items:
        return None

    standards = {}

    for field in fields:
        standards[field] = mode_value(
            items,
            field
        )

    issues = []

    for item in items:
        for field in fields:
            expected = standards.get(field)
            actual = item.get(field)

            if not expected or not actual:
                continue

            if actual != expected:
                issues.append(
                    build_issue(
                        item=item,
                        group_name=name,
                        field=field,
                        actual=actual,
                        expected=expected,
                    )
                )

    affected_elements = {
        (
            issue["text"],
            issue["tag"],
        )
        for issue in issues
    }

    issue_element_count = len(
        affected_elements
    )

    return {
        "name": name,
        "category": category,
        "total": len(items),
        "standards": standards,
        "issues": issues,
        "issue_count": len(issues),
        "affected_elements": issue_element_count,
        "score": score_from_issues(
            len(items),
            issue_element_count,
        ),
        "is_consistent": (
            issue_element_count == 0
        ),
    }


def classify_button(item):
    background = item.get(
        "background_color"
    )
    border_width = parse_px(
        item.get("border_width")
    )
    tag = item.get("tag")

    if tag == "a":
        role = "link-button"
    else:
        role = "button"

    transparent_values = {
        "rgba(0, 0, 0, 0)",
        "transparent",
    }

    has_background = (
        background
        and background not in transparent_values
    )

    if has_background:
        return f"{role}-filled"

    if border_width and border_width > 0:
        return f"{role}-outline"

    return f"{role}-text"


def classify_link(item):
    classes = (
        item.get("class_name") or ""
    ).lower()

    parent_tag = (
        item.get("parent_tag") or ""
    ).lower()

    if (
        "nav" in classes
        or parent_tag == "nav"
    ):
        return "Navigation Links"

    if "footer" in classes:
        return "Footer Links"

    if (
        "btn" in classes
        or "button" in classes
    ):
        return "Button Links"

    return "Content Links"


# =========================================================
# DESIGN TOKEN EXTRACTION
# =========================================================

def collect_common_tokens(
    all_items,
    field,
    limit=8,
):
    values = [
        item.get(field)
        for item in all_items
        if item.get(field)
        not in (
            None,
            "",
            "normal",
            "none",
            "0px",
            "rgba(0, 0, 0, 0)",
            "transparent",
        )
    ]

    return [
        {
            "value": value,
            "count": count,
        }
        for value, count in Counter(
            values
        ).most_common(limit)
    ]


# =========================================================
# SCAN WEBSITE
# =========================================================

def scan_website(url):

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200,
            }
        )

        page.goto(
            url,
            wait_until="networkidle",
            timeout=60000,
        )

        data = page.evaluate(
            """
            () => {

                function isVisible(el) {
                    const style =
                        window.getComputedStyle(el);

                    const rect =
                        el.getBoundingClientRect();

                    return (
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        parseFloat(style.opacity) !== 0 &&
                        rect.width > 0 &&
                        rect.height > 0
                    );
                }


                function cleanText(el) {
                    return (
                        el.innerText ||
                        el.value ||
                        el.textContent ||
                        ''
                    )
                    .replace(/\\s+/g, ' ')
                    .trim()
                    .slice(0, 180);
                }


                function elementData(el) {

                    const style =
                        window.getComputedStyle(el);

                    const rect =
                        el.getBoundingClientRect();

                    return {

                        tag:
                            el.tagName.toLowerCase(),

                        text:
                            cleanText(el),

                        class_name:
                            el.className
                                ? String(el.className)
                                : '',

                        parent_tag:
                            el.parentElement
                                ? el.parentElement
                                    .tagName
                                    .toLowerCase()
                                : '',


                        font_size:
                            style.fontSize,

                        font_weight:
                            style.fontWeight,

                        line_height:
                            style.lineHeight,

                        font_family:
                            style.fontFamily,

                        letter_spacing:
                            style.letterSpacing,

                        text_transform:
                            style.textTransform,


                        color:
                            style.color,

                        background_color:
                            style.backgroundColor,


                        border_radius:
                            style.borderRadius,

                        border_width:
                            style.borderWidth,

                        border_color:
                            style.borderColor,

                        border_style:
                            style.borderStyle,


                        padding_top:
                            style.paddingTop,

                        padding_right:
                            style.paddingRight,

                        padding_bottom:
                            style.paddingBottom,

                        padding_left:
                            style.paddingLeft,


                        margin_top:
                            style.marginTop,

                        margin_right:
                            style.marginRight,

                        margin_bottom:
                            style.marginBottom,

                        margin_left:
                            style.marginLeft,


                        gap:
                            style.gap,

                        display:
                            style.display,

                        justify_content:
                            style.justifyContent,

                        align_items:
                            style.alignItems,


                        width:
                            `${Math.round(rect.width)}px`,

                        height:
                            `${Math.round(rect.height)}px`,

                        top:
                            Math.round(rect.top),

                        left:
                            Math.round(rect.left),


                        box_shadow:
                            style.boxShadow,
                    };
                }


                function collect(selector) {
                    return Array
                        .from(
                            document
                            .querySelectorAll(
                                selector
                            )
                        )
                        .filter(isVisible)
                        .map(elementData);
                }


                const headings =
                    collect(
                        'h1,h2,h3,h4,h5,h6'
                    );

                const paragraphs =
                    collect(
                        'p'
                    );

                const buttons =
                    collect(
                        [
                            'button',
                            'input[type="submit"]',
                            'input[type="button"]',
                            'a[class*="btn"]',
                            'a[class*="button"]',
                            '[role="button"]'
                        ].join(',')
                    );

                const links =
                    collect('a');

                const inputs =
                    collect(
                        [
                            'input:not([type="submit"])',
                            'textarea',
                            'select'
                        ].join(',')
                    );

                const sections =
                    collect(
                        [
                            'section',
                            'main > section',
                            'main > div'
                        ].join(',')
                    );

                const cards =
                    collect(
                        [
                            '[class*="card"]',
                            '[class*="Card"]',
                            'article'
                        ].join(',')
                    );


                return {
                    headings,
                    paragraphs,
                    buttons,
                    links,
                    inputs,
                    sections,
                    cards,
                };
            }
            """
        )

        browser.close()


    # =====================================================
    # TYPOGRAPHY
    # =====================================================

    reports = []

    for tag in [
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    ]:
        items = [
            item
            for item in data["headings"]
            if item["tag"] == tag
        ]

        report = build_group_report(
            name=tag.upper(),
            items=items,
            fields=[
                "font_size",
                "font_weight",
                "line_height",
                "font_family",
            ],
            category="typography",
        )

        if report:
            reports.append(report)


    body_report = build_group_report(
        name="Body Text",
        items=data["paragraphs"],
        fields=[
            "font_size",
            "font_weight",
            "line_height",
            "font_family",
        ],
        category="typography",
    )

    if body_report:
        reports.append(body_report)


    # =====================================================
    # BUTTON CLUSTERING
    # =====================================================

    button_groups = defaultdict(list)

    for item in data["buttons"]:
        button_groups[
            classify_button(item)
        ].append(item)

    for group_name, items in (
        button_groups.items()
    ):

        display_name = (
            group_name
            .replace("-", " ")
            .title()
        )

        report = build_group_report(
            name=display_name,
            items=items,
            fields=[
                "font_size",
                "font_weight",
                "height",
                "border_radius",
                "background_color",
                "color",
            ],
            category="components",
        )

        if report:
            reports.append(report)


    # =====================================================
    # LINK CLUSTERING
    # =====================================================

    link_groups = defaultdict(list)

    for item in data["links"]:
        link_groups[
            classify_link(item)
        ].append(item)

    for group_name, items in (
        link_groups.items()
    ):

        report = build_group_report(
            name=group_name,
            items=items,
            fields=[
                "font_size",
                "font_weight",
                "color",
            ],
            category="components",
        )

        if report:
            reports.append(report)


    # =====================================================
    # INPUTS
    # =====================================================

    input_report = build_group_report(
        name="Form Fields",
        items=data["inputs"],
        fields=[
            "font_size",
            "height",
            "border_radius",
            "border_width",
            "background_color",
        ],
        category="components",
    )

    if input_report:
        reports.append(input_report)


    # =====================================================
    # CARDS
    # =====================================================

    card_report = build_group_report(
        name="Cards",
        items=data["cards"],
        fields=[
            "border_radius",
            "background_color",
            "box_shadow",
        ],
        category="components",
    )

    if card_report:
        reports.append(card_report)


    # =====================================================
    # SECTIONS
    # =====================================================

    section_report = build_group_report(
        name="Section Spacing",
        items=data["sections"],
        fields=[
            "padding_top",
            "padding_bottom",
        ],
        category="spacing",
    )

    if section_report:
        reports.append(
            section_report
        )


    # =====================================================
    # DESIGN TOKENS
    # =====================================================

    all_items = (
        data["headings"]
        + data["paragraphs"]
        + data["buttons"]
        + data["links"]
        + data["inputs"]
        + data["sections"]
        + data["cards"]
    )

    design_tokens = {

        "font_sizes":
            collect_common_tokens(
                all_items,
                "font_size",
            ),

        "font_weights":
            collect_common_tokens(
                all_items,
                "font_weight",
            ),

        "colors":
            collect_common_tokens(
                all_items,
                "color",
            ),

        "backgrounds":
            collect_common_tokens(
                all_items,
                "background_color",
            ),

        "radii":
            collect_common_tokens(
                all_items,
                "border_radius",
            ),

        "padding_top":
            collect_common_tokens(
                data["sections"],
                "padding_top",
            ),

        "padding_bottom":
            collect_common_tokens(
                data["sections"],
                "padding_bottom",
            ),
    }


    # =====================================================
    # CATEGORY SCORES
    # =====================================================

    category_reports = defaultdict(list)

    for report in reports:
        category_reports[
            report["category"]
        ].append(report)


    category_scores = {}

    for category, items in (
        category_reports.items()
    ):

        category_scores[
            category
        ] = round(
            sum(
                report["score"]
                for report in items
            )
            / len(items)
        )


    # =====================================================
    # ALL ISSUES
    # =====================================================

    all_issues = []

    for report in reports:
        all_issues.extend(
            report["issues"]
        )


    severity_counts = {
        "major": 0,
        "moderate": 0,
        "minor": 0,
    }

    for issue in all_issues:
        severity = issue["severity"]

        severity_counts[
            severity
        ] += 1


    # =====================================================
    # WEIGHTED SCORE
    # =====================================================

    typography_score = (
        category_scores.get(
            "typography",
            100,
        )
    )

    component_score = (
        category_scores.get(
            "components",
            100,
        )
    )

    spacing_score = (
        category_scores.get(
            "spacing",
            100,
        )
    )


    overall_score = round(
        typography_score * 0.40
        + component_score * 0.35
        + spacing_score * 0.25
    )


    # =====================================================
    # RATING
    # =====================================================

    if overall_score >= 90:
        rating = "Excellent"

    elif overall_score >= 80:
        rating = "Good"

    elif overall_score >= 70:
        rating = "Fair"

    elif overall_score >= 60:
        rating = "Needs Improvement"

    else:
        rating = "Poor"


    return {
        "url": url,

        "overall_score":
            overall_score,

        "rating":
            rating,

        "total_issues":
            len(all_issues),

        "severity_counts":
            severity_counts,

        "category_scores":
            category_scores,

        "reports":
            reports,

        "all_issues":
            all_issues,

        "design_tokens":
            design_tokens,

        "stats": {
            "headings":
                len(data["headings"]),

            "paragraphs":
                len(data["paragraphs"]),

            "buttons":
                len(data["buttons"]),

            "links":
                len(data["links"]),

            "inputs":
                len(data["inputs"]),

            "sections":
                len(data["sections"]),

            "cards":
                len(data["cards"]),
        },
    }