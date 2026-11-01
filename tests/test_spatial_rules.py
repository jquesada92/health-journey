from inbody_mvp.spatial_rules import match_spatial_pairs, SECTION_DIRECTIONS

def box(text,x,y,w=.09,h=.008):
    return ([[x*1000,y*1000],[(x+w)*1000,y*1000],[(x+w)*1000,(y+h)*1000],[x*1000,(y+h)*1000]],text,.98)

def test_header_vertical():
    tokens=[box("ID",.12,.04),box("ABC123456",.12,.065),box("Edad",.55,.04),box("34",.55,.065)]
    matches=match_spatial_pairs(tokens,1000,1000,direction="top_to_bottom",region=(0,0,1,.15),labels=("ID","Edad"),tolerance=.018)
    assert [(m.label.text,m.value.text) for m in matches] == [("ID","ABC123456"),("Edad","34")]

def test_muscle_fat_horizontal_preserves_decimal():
    tokens=[box("Peso",.08,.22),box("8.20 kg",.32,.22),box("Masa muscular",.08,.26),box("32.1 kg",.32,.26)]
    matches=match_spatial_pairs(tokens,1000,1000,direction="left_to_right",region=(0,.2,.8,.3),labels=("Peso","Masa muscular"),max_gap=.25)
    assert [(m.label.text,m.value.text) for m in matches]==[("Peso","8.20 kg"),("Masa muscular","32.1 kg")]

def test_does_not_take_other_row_or_outside_section():
    tokens=[box("Peso",.08,.22),box("75 kg",.32,.28),box("77 kg",.32,.50)]
    assert not match_spatial_pairs(tokens,1000,1000,direction="left_to_right",region=(0,.2,.8,.3),labels=("Peso",),max_gap=.25)

def test_section_configuration():
    assert SECTION_DIRECTIONS["header"]=="top_to_bottom"
    assert SECTION_DIRECTIONS["muscle_fat"]=="left_to_right"
