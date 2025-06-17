from lxml import etree


def load_xml(xml):
    if not isinstance(xml, bytes):
        xml = xml.encode("utf-8")
    root = etree.fromstring(xml)
    for elem in root.getiterator():
        if not hasattr(elem.tag, "find"):
            # e.g. comment elements
            continue
        elem.tag = etree.QName(elem).localname
    etree.cleanup_namespaces(root)
    return root
