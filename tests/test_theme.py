from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]

def ratio(a,b):
    def lum(h):
        rgb=[int(h[i:i+2],16)/255 for i in (1,3,5)]
        return sum((x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4)*w for x,w in zip(rgb,(.2126,.7152,.0722)))
    x,y=sorted((lum(a),lum(b)))
    return (y+.05)/(x+.05)

class ThemeTests(unittest.TestCase):
    def test_palette_and_accessible_pairs(self):
        css=(ROOT/'ui/theme.css').read_text()
        colors=dict(re.findall(r'--ieum-([a-z-]+):(#[0-9a-f]{6});',css))
        self.assertEqual(colors['red'],'#ea002c')
        self.assertEqual(colors['orange'],'#ff7a00')
        for a,b in [('white','red'),('ink','white'),('muted','white'),('ink','warm'),('link','white')]:
            self.assertGreaterEqual(ratio(colors[a],colors[b]),4.5,(a,b))
    def test_shared_theme_loaded_and_old_brand_removed(self):
        for file in ['gangseo_app.py','ui/seongsan_app.py']:
            self.assertIn("ui/theme.css",(ROOT/file).read_text())
        for file in ['chat.css','discovery.css','seongsan_light.css']:
            css=(ROOT/'ui'/file).read_text()
            self.assertIn('var(--ieum-',css)
            self.assertNotRegex(css,r'#(?:124d78|10375c|075985|eaf4ff)')
