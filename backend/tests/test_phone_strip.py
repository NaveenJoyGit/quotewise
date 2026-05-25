from app.services.whatsapp.phone import strip_whatsapp_prefix


def test_strip_whatsapp_prefix():
    assert strip_whatsapp_prefix("whatsapp:+919999900001") == "+919999900001"
    assert strip_whatsapp_prefix("+919999900001") == "+919999900001"
