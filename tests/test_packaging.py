import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from package_release import package
from check_package import verify
from restore_package import restore

class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        boundary=ROOT/'.artifacts/packages';boundary.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(dir=boundary);cls.root=Path(cls.temp.name)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_maintenance_restore_and_tamper_detection(self):
        source=self.root/'maintenance';m=package(source,mode='maintenance')
        self.assertNotIn('db/sam14.db',m['files']);self.assertEqual(verify(source,True)['mode'],'maintenance')
        recovered=restore(source,self.root/'restored');self.assertEqual(verify(recovered)['files'],m['files'])
        (recovered/'unexpected.s14').write_bytes(b'not allowed')
        with self.assertRaisesRegex(ValueError,'Unexpected'):verify(recovered)
        (source/'api/index.py').write_text('tampered',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'mismatch'):verify(source)
    def test_unverified_release_and_external_paths_rejected(self):
        database=ROOT/'db/ce-24966116-r3.final.db'
        with self.assertRaisesRegex(ValueError,'Release gate'):package(self.root/'blocked',database)
        self.assertFalse((self.root/'blocked').exists())
        with self.assertRaises(ValueError):package(ROOT/'reports/invalid-package',mode='maintenance')
        with self.assertRaises(ValueError):restore(ROOT,ROOT/'reports/restore')
    def test_missing_database_entrypoint_fails_closed(self):
        spec=importlib.util.spec_from_file_location('ce_deployment_entry',ROOT/'api/index.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertIs(module.handler,module.MaintenanceHandler)
