import fitz  # PyMuPDF


def extract_pdf_sections_by_headings(pdf_path):
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()

    if not toc:
        raise ValueError("No TOC found in the PDF.")

    # Prepare list of (title, page number, y-position of heading)
    section_markers = []

    for level, title, page_num in toc:
        page_index = page_num - 1
        page = doc[page_index]
        found = False
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                line_text = " ".join(span["text"] for span in line["spans"])
                if title.strip().lower() in line_text.strip().lower():
                    bbox = block["bbox"]
                    section_markers.append(
                        {"title": title, "page": page_index, "y": bbox[1]}
                    )
                    found = True
                    break
            if found:
                break
        if not found:
            # Fallback: assume top of page if heading not detected
            section_markers.append({"title": title, "page": page_index, "y": 0})

    # Sort section markers by page then y
    section_markers.sort(key=lambda x: (x["page"], x["y"]))
    sections = {}

    # Handle all pairs
    for curr, next_ in zip(section_markers, section_markers[1:], strict=False):
        sections[curr["title"]] = extract_section_content(doc, curr, next_)

    # Handle last section — from its position to the end of the doc
    last = section_markers[-1]
    sections[last["title"]] = extract_section_content(doc, last, None)

    return toc, sections


def extract_section_content(doc, curr, next_):
    start_page, start_y = curr["page"], curr["y"]
    if next_:
        end_page, end_y = next_["page"], next_["y"]
    else:
        end_page, end_y = len(doc) - 1, None

    content = ""

    for page_num in range(start_page, end_page + 1):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            y = block["bbox"][1]

            # Filtering by y-position only when on start or end page
            if page_num == start_page and y < start_y:
                continue
            if page_num == end_page and end_y is not None and y >= end_y:
                continue

            text = "".join(
                span["text"]
                for line in block.get("lines", [])
                for span in line["spans"]
            )
            content += text + "\n"

    return content.strip()


# === Example usage ===
if __name__ == "__main__":
    pdf_file = "example/test_markdown.pdf"  # Replace with your file
    toc, sections = extract_pdf_sections_by_headings(pdf_file)

    print("TABLE OF CONTENTS:\n")
    for level, title, page in toc:
        print(f"{'  ' * (level - 1)}- {title} (Page {page})")

    print("\n\nSECTION CONTENT PREVIEWS:\n")
    for title, text in sections.items():
        print(f"\n=== {title} ===\n{text[:1000]}\n{'-'*60}")
