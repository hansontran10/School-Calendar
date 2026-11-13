"""Builds a minimal text PDF in memory, so tests do not need fixture files or extra packages."""


def make_pdf(lines: list[str]) -> bytes:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    body = ["BT", "/F1 11 Tf", "14 TL", "50 750 Td"]
    for line in lines:
        body.append(f"({esc(line)}) Tj T*")
    body.append("ET")
    stream = "\n".join(body).encode()

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


SAMPLE_LINES = [
    "BIO 101 - Introduction to Biology - Spring 2027",
    "Instructor: Dr. Example. Office hours Tuesdays 2-4pm.",
    "Grading: labs 30%, exams 50%, project 20%.",
    "Schedule of graded work:",
    "Lab Report 1 due Friday, January 22 at 11:59pm on Moodle.",
    "Exam 1 in class on Thursday, February 18.",
    "Group project proposal due Week 8 Monday.",
    "Final exam: date TBA by the registrar.",
    "No class on March 8-12 (spring break).",
]
