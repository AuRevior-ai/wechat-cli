# Third-party notices

## silk-v3-decoder

- Project: `kn007/silk-v3-decoder`
- Source: https://github.com/kn007/silk-v3-decoder
- Bundled file: `wechat_cli/bin/silk_v3_decoder.exe`
- SHA-256: `afe908fdf8bb5ddc3566caef224a365159a6216e517d8a915db50ce5ecf86d1b`
- License: MIT

Copyright (c) 2015 KN007

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## sherpa-onnx

- Project: `k2-fsa/sherpa-onnx`
- Source: https://github.com/k2-fsa/sherpa-onnx
- Version used on Windows: 1.13.4
- License: Apache License 2.0
- Runtime archive SHA-256: `e33dc64195d17601879532583233d0d6ed76aa399eb863e5ca0783c5ac82b5aa`

The runtime is not embedded in the WeChat CLI executable. It is downloaded
from the project's official GitHub release on first voice transcription,
verified with the SHA-256 value above, and then cached locally.

## Paraformer Chinese offline ASR model

- Distribution: `sherpa-onnx-paraformer-zh-small-2024-03-09`
- Distribution source: https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models
- Original model source: https://www.modelscope.cn/models/crazyant/speech_paraformer_asr_nat-zh-cn-16k-common-vocab8358-onnx/summary
- Archive SHA-256: `da92b3db5218c5be53aad53e57d1b6e63e7fc98a0e054fbdd6dbe18e9c6b1450`

The model is not embedded in the WeChat CLI executable. It is downloaded on
first use, verified with the SHA-256 value above, and cached for offline use.
The model's upstream terms remain applicable.
