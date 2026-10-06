import unittest
from unittest.mock import patch

import main


class MainTests(unittest.TestCase):
    @patch("main.run_server")
    def test_main_default_host_and_port(self, mock_run_server):
        with patch.dict("os.environ", {}, clear=True):
            exit_code = main.main()
            self.assertEqual(exit_code, 0)
            mock_run_server.assert_called_once_with(host="0.0.0.0", port=8080)

    @patch("main.run_server")
    def test_main_custom_host_and_port(self, mock_run_server):
        exit_code = main.main(host="127.0.0.1", port=9000)
        self.assertEqual(exit_code, 0)
        mock_run_server.assert_called_once_with(host="127.0.0.1", port=9000)

    @patch("main.run_server")
    def test_main_env_vars(self, mock_run_server):
        with patch.dict("os.environ", {"HOST": "10.0.0.1", "PORT": "8888"}):
            exit_code = main.main()
            self.assertEqual(exit_code, 0)
            mock_run_server.assert_called_once_with(host="10.0.0.1", port=8888)
