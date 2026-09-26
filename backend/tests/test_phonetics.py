from __future__ import annotations

from app.domain.phonetics import apply_phonetic_transliteration


def test_phonetic_transliteration_authorities():
    text = "SBCA approved project with LDA and CDA NOC verified by FBR."
    result = apply_phonetic_transliteration(text)
    assert "S B C A" in result
    assert "L D A" in result
    assert "C D A" in result
    assert "N O C" in result
    assert "F B R" in result


def test_phonetic_transliteration_tax_sections():
    text = "Purchaser advance tax 236K aur seller tax 236C lagta hai. Section 7E bhi check karein."
    result = apply_phonetic_transliteration(text)
    assert "236 K" in result
    assert "236 C" in result
    assert "Section 7 E" in result


def test_phonetic_transliteration_localities():
    text = "DHA Karachi Khayaban-e-Bukhari aur Shahrah-e-Faisal pe Sector F-6 aur E-11 options hain."
    result = apply_phonetic_transliteration(text)
    assert "Khayaban e Bukhari" in result
    assert "Shahrah e Faisal" in result
    assert "Sector F 6" in result
    assert "E 11" in result


def test_phonetic_transliteration_units_and_currency():
    text = "Ye 2000 sqft apartment PKR 3.5 Crore ka hai, aur 500 sqyd plot Rs. 85 Lakh ka hai."
    result = apply_phonetic_transliteration(text)
    assert "square feet" in result
    assert "square yards" in result
    assert "3.5 crore rupay" in result
    assert "85 lakh rupay" in result


def test_phonetic_transliteration_empty_or_whitespace():
    assert apply_phonetic_transliteration("") == ""
    assert apply_phonetic_transliteration("   ") == "   "
