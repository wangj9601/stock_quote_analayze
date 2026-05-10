# 远程部署 / 生产 pip 安装：requirements-prod.txt 仅允许两条 -r 指向
# backend_api/requirements-minimal.txt 与 backend_core/requirements-minimal.txt，
# 禁止 full 清单或其它行（避免装入 xhtml2pdf、torch、tensorflow 等）。
function Assert-RequirementsProdMinimalDeps {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RequirementsProdPath
    )
    if (-not (Test-Path -LiteralPath $RequirementsProdPath)) {
        throw "requirements-prod.txt not found: $RequirementsProdPath"
    }
    $content = Get-Content -LiteralPath $RequirementsProdPath -Encoding UTF8
    $hasApiMinimal = $false
    $hasCoreMinimal = $false
    foreach ($raw in $content) {
        $line = $raw.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) {
            continue
        }
        if ($line -match '^\s*-r\s+backend_api/requirements-minimal\.txt\s*$') {
            $hasApiMinimal = $true
        }
        elseif ($line -match '^\s*-r\s+backend_core/requirements-minimal\.txt\s*$') {
            $hasCoreMinimal = $true
        }
        elseif ($line -match '^\s*-r\s+backend_api/requirements\.txt\s*$') {
            throw ("requirements-prod.txt 禁止 -r backend_api/requirements.txt，请仅使用 -r backend_api/requirements-minimal.txt。File: {0}" -f $RequirementsProdPath)
        }
        elseif ($line -match '^\s*-r\s+backend_core/requirements\.txt\s*$') {
            throw ("requirements-prod.txt 禁止 -r backend_core/requirements.txt，请仅使用 -r backend_core/requirements-minimal.txt。File: {0}" -f $RequirementsProdPath)
        }
        else {
            throw ("requirements-prod.txt 仅允许两条 minimal 的 -r 与注释，禁止其它依赖行（避免装入机器学习等库）。非法行: {0} (File: {1})" -f $line, $RequirementsProdPath)
        }
    }
    if (-not $hasApiMinimal) {
        throw ("requirements-prod.txt 必须包含: -r backend_api/requirements-minimal.txt (File: {0})" -f $RequirementsProdPath)
    }
    if (-not $hasCoreMinimal) {
        throw ("requirements-prod.txt 必须包含: -r backend_core/requirements-minimal.txt (File: {0})" -f $RequirementsProdPath)
    }
}
