/**
 * dsh-sts2-agent —— 让 AI 轻松玩《杀戮尖塔 2》的 DSH 插件
 *
 * 思路：不碰游戏内存、不装 mod。用一张截图（AI 能看）＋ 鼠标键盘注入（AI 能点），
 * 把「看一眼 → 点一下」这件事包成工具，同时把每一步记进一份可读的运行日志。
 */
import { spawnSync } from 'node:child_process'
import { appendFileSync, mkdirSync, existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { loadHostDeps } from './lib/hostdeps.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const HELPER = join(HERE, 'lib', 'sts2.py')

let PKG = { version: '0.1.0' }
try {
  PKG = JSON.parse(readFileSync(join(HERE, 'package.json'), 'utf8'))
} catch {}

const hostDeps = await loadHostDeps()
const defineTool = hostDeps.defineTool

export const name = 'sts2-agent'
export const inject = ['tools']
export const Config = undefined

const DEFAULTS = {
  enabled: true,
  pythonPath: '',
  windowTitle: 'Slay the Spire 2',
  shotsDir: '',
  logFile: '',
  cardsFile: '',
}

function dshHome() {
  return process.env.DSH_HOME || join(homedir(), '.dsh')
}

function resolvePaths(cfg) {
  const base = join(dshHome(), 'sts2')
  const shotsDir = cfg.shotsDir ? resolve(cfg.shotsDir) : join(base, 'shots')
  const logFile = cfg.logFile ? resolve(cfg.logFile) : join(base, 'run-log.md')
  const cardsFile = cfg.cardsFile ? resolve(cfg.cardsFile) : join(base, 'data', 'index.tsv')
  return { base, shotsDir, logFile, cardsFile }
}

/** 在本地牌表里按名字/效果模糊查：名称 \t 类型 \t 效果 \t ID */
function lookupCards(cfg, query, typeFilter, limit) {
  const { cardsFile } = resolvePaths(cfg)
  if (!existsSync(cardsFile)) return { ok: false, error: `没有牌表文件：${cardsFile}`, hint: '用 tools/build-db.py 从游戏 pck 生成一份，再把 cardsFile 指过去' }
  const needle = String(query || '').toLowerCase()
  const rows = []
  for (const line of readFileSync(cardsFile, 'utf8').split('\n')) {
    const parts = line.split('\t')
    if (parts.length < 3) continue
    const [name, type, desc] = parts
    const cid = parts[3] || ''
    if (typeFilter && !type.includes(typeFilter)) continue
    if (!`${name} ${desc} ${cid}`.toLowerCase().includes(needle)) continue
    rows.push({ name, type, desc: desc.trim(), id: cid })
  }
  rows.sort((a, b) => (a.name === query ? -1 : b.name === query ? 1 : 0))
  return { ok: true, total: rows.length, hits: rows.slice(0, limit) }
}

function pythonOf(cfg) {
  return cfg.pythonPath || process.env.STS2_PYTHON || 'python'
}

function runHelper(cfg, args, timeoutMs = 20000) {
  const res = spawnSync(pythonOf(cfg), [HELPER, ...args], {
    encoding: 'utf8',
    timeout: timeoutMs,
    windowsHide: true,
    env: {
      ...process.env,
      STS2_TITLE: cfg.windowTitle || DEFAULTS.windowTitle,
      PYTHONIOENCODING: 'utf-8',
    },
  })
  const out = (res.stdout || '').trim()
  const err = (res.stderr || '').trim()
  if (res.error) return { ok: false, error: String(res.error.message || res.error), out }
  if (res.status !== 0) return { ok: false, error: err || `exit ${res.status}`, out }
  return { ok: true, out, err }
}

function stamp() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function logLine(cfg, line) {
  try {
    const { logFile } = resolvePaths(cfg)
    mkdirSync(dirname(logFile), { recursive: true })
    if (!existsSync(logFile)) appendFileSync(logFile, '# 杀戮尖塔 2 · AI 游玩记录\n\n')
    appendFileSync(logFile, `- ${stamp()} ${line}\n`)
    return logFile
  } catch {
    return null
  }
}

export function apply(ctx, rawConfig = {}) {
  // 配置文件优先于 cordis 里的 config，方便不重启改参数（下次启动生效）
  let fileCfg = {}
  try {
    const f = join(dshHome(), 'sts2', 'config.json')
    if (existsSync(f)) fileCfg = JSON.parse(readFileSync(f, 'utf8'))
  } catch {}
  const cfg = { ...DEFAULTS, ...(rawConfig || {}), ...fileCfg }
  const { shotsDir, logFile } = resolvePaths(cfg)
  mkdirSync(shotsDir, { recursive: true })

  const output = {
    schema: { type: 'object', properties: {}, additionalProperties: true },
    render: (_a, v) => [{ type: 'text', text: typeof v === 'string' ? v : JSON.stringify(v, null, 2) }],
  }

  const tool = (spec) =>
    ctx.tools.register(
      defineTool({
        ...spec,
        output,
        async execute(args, exec) {
          try {
            return await spec.execute(args || {}, exec)
          } catch (e) {
            return { ok: false, error: String((e && e.message) || e) }
          }
        },
      }),
    )

  tool({
    name: 'sts2_shot',
    description:
      '截一张《杀戮尖塔 2》游戏窗口的图（返回 PNG 路径，用 read_image 看）。label 会写进游玩日志，比如「第3层 战斗开始」。',
    parameters: {
      label: { type: 'string', description: '给这张截图起的说明（可选），会记进日志' },
    },
    async execute(args = {}) {
      const file = join(shotsDir, `shot-${Date.now()}.png`)
      const r = runHelper(cfg, ['shot', file])
      if (!r.ok) return { ok: false, error: r.error }
      logLine(cfg, `📷 截图${args.label ? '：' + args.label : ''} → ${file}`)
      const m = /(\d+)x(\d+) @ (-?\d+),(-?\d+)/.exec(r.out)
      return {
        ok: true,
        path: file,
        width: m ? Number(m[1]) : null,
        height: m ? Number(m[2]) : null,
        originX: m ? Number(m[3]) : 0,
        originY: m ? Number(m[4]) : 0,
        hint: '用 read_image 打开这个路径；点击坐标 = 图内像素 + originX/originY',
      }
    },
  })

  tool({
    name: 'sts2_click',
    description:
      '在屏幕坐标点一下（鼠标左键）。坐标是屏幕绝对坐标：图内像素 + sts2_shot 返回的 originX/originY。note 会记进日志。',
    parameters: {
      x: { type: 'number', required: true, description: '屏幕 X 坐标' },
      y: { type: 'number', required: true, description: '屏幕 Y 坐标' },
      note: { type: 'string', description: '这一步在干什么（可选），会记进日志' },
    },
    async execute(args = {}) {
      if (typeof args.x !== 'number' || typeof args.y !== 'number') return { ok: false, error: '需要数字 x/y' }
      const r = runHelper(cfg, ['click', String(Math.round(args.x)), String(Math.round(args.y))])
      if (!r.ok) return { ok: false, error: r.error }
      if (args.note) logLine(cfg, `🖱️ 点击 (${Math.round(args.x)},${Math.round(args.y)})：${args.note}`)
      return { ok: true, x: Math.round(args.x), y: Math.round(args.y) }
    },
  })

  tool({
    name: 'sts2_drag',
    description:
      '按住鼠标从 (x1,y1) 拖到 (x2,y2)。杀戮尖塔里出牌是「把卡从手牌拖到屏幕上方」，打向敌人则拖到敌人身上——所以这个是出牌主工具，x,y 都是屏幕绝对坐标。',
    parameters: {
      x1: { type: 'number', required: true, description: '起点 X（手牌位置）' },
      y1: { type: 'number', required: true, description: '起点 Y（手牌位置）' },
      x2: { type: 'number', required: true, description: '终点 X（上方空地区域 ≈ y=420；打敌人时拖到敌人身上）' },
      y2: { type: 'number', required: true, description: '终点 Y' },
      note: { type: 'string', description: '这一步在干什么（可选），会记进日志' },
    },
    async execute(args = {}) {
      const ok = ['x1', 'y1', 'x2', 'y2'].every((k) => typeof args[k] === 'number')
      if (!ok) return { ok: false, error: '需要数字 x1/y1/x2/y2' }
      const r = runHelper(
        cfg,
        ['drag', ...[args.x1, args.y1, args.x2, args.y2].map((v) => String(Math.round(v)))],
        30000,
      )
      if (!r.ok) return { ok: false, error: r.error }
      if (args.note) logLine(cfg, `🐉 拖拽 (${Math.round(args.x1)},${Math.round(args.y1)}) → (${Math.round(args.x2)},${Math.round(args.y2)})：${args.note}`)
      return { ok: true }
    },
  })

  tool({
    name: 'sts2_key',
    description: '按一个键（enter/space/escape/tab/up/down/left/right/数字/字母）。用来结束回合、确认、开地图。',
    parameters: {
      key: { type: 'string', required: true, description: '键名' },
      note: { type: 'string', description: '这一步在干什么（可选）' },
    },
    async execute(args = {}) {
      if (!args.key) return { ok: false, error: '需要 key' }
      const r = runHelper(cfg, ['key', String(args.key)])
      if (!r.ok) return { ok: false, error: r.error }
      if (args.note) logLine(cfg, `⌨️ 按键 ${args.key}：${args.note}`)
      return { ok: true, key: args.key }
    },
  })

  tool({
    name: 'sts2_log',
    description: '往游玩日志里写一行（决策理由、血量、战利品之类的要点）。',
    parameters: {
      line: { type: 'string', required: true, description: '要记的内容' },
    },
    async execute(args = {}) {
      if (!args.line) return { ok: false, error: '需要 line' }
      const file = logLine(cfg, String(args.line))
      return { ok: Boolean(file), file }
    },
  })

  tool({
    name: 'sts2_lookup',
    description:
      '查本地牌表：输入卡牌/遗物/能力/药水的名字或效果关键词，返回名称、类型、效果原文。出牌前先查一下，别凭印象。',
    parameters: {
      query: { type: 'string', required: true, description: '名字或效果关键词，比如「群星之子」「力量」' },
      type: { type: 'string', description: '只看某一类：卡牌 / 遗物 / 能力 / 药水 / 附魔 / 关键词（可选）' },
      limit: { type: 'number', description: '最多返回几条，默认 6' },
    },
    async execute(args = {}) {
      const limit = Math.max(1, Math.min(30, Number(args.limit) || 6))
      const r = lookupCards(cfg, args.query, args.type, limit)
      if (!r.ok) return r
      return { ok: true, query: args.query, total: r.total, hits: r.hits }
    },
  })

  tool({
    name: 'sts2_status',
    description: '看插件状态：窗口在不在、截图/日志路径、python 通不通。',
    parameters: {},
    async execute() {
      const info = runHelper(cfg, ['info'], 15000)
      return {
        ok: info.ok,
        version: PKG.version || '0.1.0',
        python: pythonOf(cfg),
        window: info.ok ? info.out : null,
        windowError: info.ok ? null : info.error,
        shotsDir,
        logFile,
        config: cfg,
      }
    },
  })
}
