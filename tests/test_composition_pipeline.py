"""Composition remains inside the transactional 1.5.9 rendering path."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from viralcut import pipeline


class CompositionPipelineTests(unittest.TestCase):
    def test_composition_finishes_before_publishing_and_preserves_metadata(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = dict(id='clip', idx=0, start=0, end=4, words=[], settings={})
            def encode(source, start, end, output, **kwargs):
                self.assertEqual(kwargs['output_size'], (1080, 1152))
                output.write_bytes(b'main')
            def compose(output, config, **kwargs):
                self.assertFalse((root/'clips/clip_01.mp4').exists())
                self.assertTrue(kwargs['main_prepared'])
                output.write_bytes(b'composed')
                return {'ad_at': 2}
            with patch('viralcut.pipeline.render.render_clip', side_effect=encode), \
                 patch('viralcut.composition.apply', side_effect=compose), \
                 patch('viralcut.pipeline.render.make_thumb', return_value=None), \
                 patch('viralcut.pipeline.render.make_preview', return_value=None), \
                 patch('viralcut.pipeline.db.update_clip') as update:
                pipeline._render_one(root/'source.mp4', root, clip, {'mode':'crop'},
                                     opts={'composition': {'game':'game.mp4'}})
            self.assertEqual((root/'clips/clip_01.mp4').read_bytes(), b'composed')
            self.assertEqual(update.call_args.kwargs['settings']['composition_info'], {'ad_at':2})
            self.assertIn('rendered_spans', update.call_args.kwargs['settings'])

    def test_failed_composition_keeps_existing_export(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'clips').mkdir()
            export=root/'clips/clip_01.mp4'; export.write_bytes(b'old')
            clip=dict(id='clip',idx=0,start=0,end=4,words=[],settings={})
            with patch('viralcut.pipeline.render.render_clip', side_effect=lambda a,b,c,out,**kw: out.write_bytes(b'new')), \
                 patch('viralcut.composition.apply', side_effect=RuntimeError('composition failed')), \
                 patch('viralcut.pipeline.db.update_clip') as update:
                with self.assertRaisesRegex(RuntimeError,'composition failed'):
                    pipeline._render_one(root/'source.mp4',root,clip,{'mode':'crop'},opts={'composition':{'logo':'logo.png'}})
            self.assertEqual(export.read_bytes(),b'old')
            update.assert_not_called()
