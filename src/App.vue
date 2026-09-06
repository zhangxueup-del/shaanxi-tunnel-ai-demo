<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import {
  Activity,
  AlertTriangle,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Database,
  Eye,
  FileCheck2,
  FileImage,
  Filter,
  History,
  Layers3,
  LocateFixed,
  MapPin,
  Maximize2,
  Network,
  PanelLeftClose,
  Play,
  Radar,
  RotateCcw,
  Route,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  UserRoundCheck,
  X,
  Zap,
  ZoomIn,
  ZoomOut,
} from 'lucide-vue-next'
import tunnels from './data/tunnels.json'
import shaanxiBoundary from './data/shaanxi-boundary.json'
import { cityAnchors, roadNetwork } from './data/road-network'

const statusMeta = {
  normal: { label: '状况良好', short: '良好', color: '#31d69b', level: 'I类' },
  attention: { label: '持续关注', short: '关注', color: '#f2c14e', level: 'II类' },
  warning: { label: '重点处置', short: '预警', color: '#ff8a4c', level: 'III类' },
  urgent: { label: '紧急复核', short: '紧急', color: '#ff5364', level: 'IV类' },
  uninspected: { label: '尚未巡检', short: '未检', color: '#7c8a9e', level: '—' },
}

const positionMeta = {
  verified: { label: '已核验坐标', className: 'verified' },
  linear: { label: '线性参考示意', className: 'linear' },
  range: { label: '范围定位示意', className: 'range' },
}

const map = ref(null)
const boundaryLayer = ref(null)
const imageryLayer = ref(null)
const referenceLayer = ref(null)
const roadLayer = ref(null)
const markerLayer = ref(null)
const labelLayer = ref(null)
const selectedTunnel = ref(tunnels.find(item => item.id === 'SX-TUN-0007') || tunnels[0])
const tiandituToken = String(import.meta.env.VITE_TIANDITU_TK || '').trim()
const mapSourceMode = ref(tiandituToken ? 'tianditu' : 'fallback')
const activeTopModule = ref('diagnosis')
const nowTime = ref('')
const nowDate = ref('')
const rightOpen = ref(true)
const leftOpen = ref(true)
const searchText = ref('')
const statusFilter = ref('all')
const routeFilter = ref('all')
const positionFilter = ref('all')
const showFilterMenu = ref(false)
const showLayerMenu = ref(false)
const showRoads = ref(true)
const showBoundary = ref(true)
const showReferenceLabels = ref(true)
const showTunnels = ref(true)
const bottomOpen = ref(false)
const selectedHistoryId = ref(null)
const activeBore = ref('up')
const selectedSectionId = ref('S02')
const mapZoom = ref(7)
const createdRecords = ref([])

const fileInput = ref(null)
const uploadedFile = ref(null)
const imagePreview = ref(null)
const boundTunnelId = ref(selectedTunnel.value.id)
const diagnosisState = ref('idle')
const diagnosisStage = ref(0)
const diagnosisResult = ref(null)
const activeResultTab = ref('result')
const savedRecord = ref(false)
const chatMessages = ref([
  {
    role: 'assistant',
    text: '你好，我是隧道病害诊断助手。上传检查图片后，我会完成影像质检、病害识别、分级诊断和处置建议。',
    time: '刚刚',
  },
])

const modelServices = [
  { name: '衬砌裂缝识别', version: 'Tunnel-Crack v2.4', metric: '92.8%', label: '验证准确率', scope: '裂缝检测、轨迹提取与宽度量化', state: '运行中' },
  { name: '渗漏水区域分割', version: 'Seepage-Seg v1.8', metric: '89.6%', label: '验证准确率', scope: '湿渍、滴漏与连续渗流区域分割', state: '运行中' },
  { name: '衬砌剥落识别', version: 'Spall-Det v1.5', metric: '87.3%', label: '验证准确率', scope: '剥落、掉块与钢筋外露目标识别', state: '运行中' },
  { name: '技术状况分级引擎', version: 'Grade-Rules 2026.3', metric: '28项', label: '分级规则', scope: '证据融合、等级判定与处置时限生成', state: '运行中' },
]

const diagnosisStages = [
  { label: '影像质量检查', detail: '清晰度、曝光、遮挡与重复帧' },
  { label: '病害区域检测', detail: '裂缝、渗漏水、剥落与露筋' },
  { label: '几何特征量化', detail: '长度、宽度、面积与位置' },
  { label: '分级诊断', detail: '规则库匹配与风险等级评估' },
  { label: '处置建议生成', detail: '复核、维修和跟踪时限' },
]

const routeOptions = computed(() => [...new Set(tunnels.map(item => item.routeCode).filter(Boolean))].sort())
const filteredTunnels = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  return tunnels.filter(item => {
    const matchesKeyword = !keyword || [item.name, item.alias, item.road, item.routeCode, item.city, item.county]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(keyword))
    const matchesStatus = statusFilter.value === 'all' || item.healthStatus === statusFilter.value
    const matchesRoute = routeFilter.value === 'all' || item.routeCode === routeFilter.value
    const matchesPosition = positionFilter.value === 'all' || item.positionType === positionFilter.value
    return matchesKeyword && matchesStatus && matchesRoute && matchesPosition
  })
})

const stats = computed(() => ({
  total: tunnels.length,
  sourceCoordinates: tunnels.filter(item => item.sourceCoordinate).length,
  concern: tunnels.filter(item => ['warning', 'urgent'].includes(item.healthStatus)).length,
  pending: tunnels.filter(item => item.healthStatus === 'uninspected').length,
}))

const currentBoundTunnel = computed(() => tunnels.find(item => item.id === boundTunnelId.value) || selectedTunnel.value)
const selectedLength = computed(() => {
  const item = selectedTunnel.value
  const values = [item.lengthLeft, item.lengthRight, item.lengthOfficial].filter(value => typeof value === 'number')
  if (!values.length) return '待补充'
  return `${Math.max(...values).toLocaleString('zh-CN')} m`
})

const selectedHistoryRows = computed(() => {
  const item = selectedTunnel.value
  const created = createdRecords.value.filter(record => record.tunnelId === item.id)
  if (!item.defectCount) {
    return [...created, { id: `JC-${item.id.slice(-4)}-01`, tunnel: item.name, disease: '常规检查', outcome: '未发现明确病害', date: item.lastInspection || '2026-03-10', level: 'I类', status: '已归档' }]
  }
  return [...created, ...[
    { id: `BH-${item.id.slice(-4)}-03`, tunnel: item.name, disease: '衬砌裂缝', outcome: '左拱腰疑似纵向裂缝', date: item.lastInspection || '2026-08-16', level: statusMeta[item.healthStatus].level, status: '待复核' },
    { id: `BH-${item.id.slice(-4)}-02`, tunnel: item.name, disease: '渗漏水', outcome: '拱顶局部潮湿带', date: '2026-05-21', level: 'II类', status: '跟踪中' },
    { id: `BH-${item.id.slice(-4)}-01`, tunnel: item.name, disease: '定期检查', outcome: '衬砌表观检查', date: '2025-11-08', level: 'I类', status: '已归档' },
  ].slice(0, Math.min(Math.max(item.defectCount, 1), 3))]
})

const mapSourceMeta = computed(() => mapSourceMode.value === 'tianditu'
  ? {
      label: '天地图影像',
      detail: '影像底图与中文注记已启用',
      state: 'online',
    }
  : {
      label: '备用开源影像',
      detail: '配置 VITE_TIANDITU_TK 后自动切换天地图',
      state: 'fallback',
    })

const tunnelLinearProfile = computed(() => {
  const status = selectedTunnel.value.healthStatus
  const reverse = activeBore.value === 'down'
  const presets = {
    normal: [
      { id: 'S01', range: 'K0+000—K0+100', state: 'normal', score: 96, defects: [] },
      { id: 'S02', range: 'K0+100—K0+200', state: 'normal', score: 94, defects: [] },
      { id: 'S03', range: 'K0+200—K0+300', state: 'normal', score: 95, defects: [] },
      { id: 'S04', range: 'K0+300—K0+400', state: 'normal', score: 93, defects: [] },
    ],
    attention: [
      { id: 'S01', range: 'K0+000—K0+100', state: 'normal', score: 92, defects: [] },
      { id: 'S02', range: 'K0+100—K0+200', state: 'attention', score: 82, defects: [{ type: '湿渍', part: '右边墙', geometry: '面', lifecycle: '既有' }] },
      { id: 'S03', range: 'K0+200—K0+300', state: 'attention', score: 79, defects: [{ type: '环向裂缝', part: '拱腰', geometry: '线', lifecycle: '新增' }] },
      { id: 'S04', range: 'K0+300—K0+400', state: 'normal', score: 91, defects: [] },
    ],
    warning: [
      { id: 'S01', range: 'K0+000—K0+100', state: 'normal', score: 90, defects: [] },
      { id: 'S02', range: 'K0+100—K0+200', state: 'warning', score: 67, defects: [{ type: '纵向裂缝', part: '左拱腰', geometry: '线', lifecycle: '发展' }, { type: '渗漏水', part: '拱顶', geometry: '面', lifecycle: '既有' }] },
      { id: 'S03', range: 'K0+200—K0+300', state: 'attention', score: 76, defects: [{ type: '湿渍', part: '右边墙', geometry: '面', lifecycle: '新增' }] },
      { id: 'S04', range: 'K0+300—K0+400', state: 'normal', score: 88, defects: [] },
    ],
    urgent: [
      { id: 'S01', range: 'K0+000—K0+100', state: 'attention', score: 75, defects: [{ type: '裂缝', part: '拱腰', geometry: '线', lifecycle: '既有' }] },
      { id: 'S02', range: 'K0+100—K0+200', state: 'urgent', score: 48, defects: [{ type: '衬砌剥落', part: '拱顶', geometry: '面', lifecycle: '发展' }, { type: '钢筋外露', part: '拱顶', geometry: '点', lifecycle: '新增' }] },
      { id: 'S03', range: 'K0+200—K0+300', state: 'warning', score: 61, defects: [{ type: '滴漏水', part: '右拱腰', geometry: '面', lifecycle: '发展' }] },
      { id: 'S04', range: 'K0+300—K0+400', state: 'attention', score: 72, defects: [{ type: '施工缝渗水', part: '边墙', geometry: '线', lifecycle: '既有' }] },
    ],
    uninspected: [
      { id: 'S01', range: 'K0+000—K0+100', state: 'uninspected', score: null, defects: [] },
      { id: 'S02', range: 'K0+100—K0+200', state: 'uninspected', score: null, defects: [] },
      { id: 'S03', range: 'K0+200—K0+300', state: 'uninspected', score: null, defects: [] },
      { id: 'S04', range: 'K0+300—K0+400', state: 'uninspected', score: null, defects: [] },
    ],
  }
  const sections = (presets[status] || presets.uninspected).map((section, index) => ({
    ...section,
    id: reverse ? `D${index + 1}` : section.id,
  }))
  return {
    coordinateNote: '相对桩号 · 100m分段 · Demo',
    sections,
  }
})

const selectedLinearSection = computed(() => tunnelLinearProfile.value.sections.find(section => section.id === selectedSectionId.value)
  || tunnelLinearProfile.value.sections[0])

const escapeHtml = value => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;')

const createMarkerIcon = tunnel => {
  const status = statusMeta[tunnel.healthStatus]
  const selected = selectedTunnel.value?.id === tunnel.id
  return L.divIcon({
    className: 'tunnel-marker-wrapper',
    html: `<div class="tunnel-marker tunnel-marker--${tunnel.healthStatus} tunnel-marker--${tunnel.positionType} ${selected ? 'is-selected' : ''}" style="--marker-color:${status.color}"><span class="marker-core"></span><span class="marker-ring"></span></div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })
}

const drawMarkers = () => {
  if (!map.value || !markerLayer.value) return
  markerLayer.value.clearLayers()
  labelLayer.value.clearLayers()
  if (!showTunnels.value) return

  filteredTunnels.value.forEach(tunnel => {
    const marker = L.marker([tunnel.latitude, tunnel.longitude], {
      icon: createMarkerIcon(tunnel),
      keyboard: true,
      title: tunnel.name,
    })
    marker.bindTooltip(
      `<div class="map-tooltip"><strong>${escapeHtml(tunnel.name)}</strong><span>${escapeHtml(tunnel.routeCode)} · ${statusMeta[tunnel.healthStatus].label}</span><em>${positionMeta[tunnel.positionType].label}</em></div>`,
      { direction: 'top', offset: [0, -12], opacity: 1 }
    )
    marker.on('click', () => selectTunnel(tunnel, true))
    marker.addTo(markerLayer.value)

    if (mapZoom.value >= 9 || selectedTunnel.value?.id === tunnel.id) {
      L.tooltip({ permanent: true, direction: 'right', className: 'tunnel-name-label', offset: [12, 0] })
        .setLatLng([tunnel.latitude, tunnel.longitude])
        .setContent(`${escapeHtml(tunnel.name)} <b>${escapeHtml(tunnel.routeCode)}</b>`)
        .addTo(labelLayer.value)
    }
  })
}

const drawRoads = () => {
  if (!map.value || !roadLayer.value) return
  roadLayer.value.clearLayers()
  if (!showRoads.value) return
  roadNetwork.forEach(road => {
    const shadow = L.polyline(road.coordinates, { color: '#172016', weight: 6, opacity: 0.72, interactive: false })
    const line = L.polyline(road.coordinates, { color: '#f2c84b', weight: 2.15, opacity: 0.88 })
    line.bindTooltip(`<strong>${road.code}</strong> ${road.name}<br><small>Demo路网示意</small>`, { sticky: true })
    shadow.addTo(roadLayer.value)
    line.addTo(roadLayer.value)
  })
}

const drawBoundary = () => {
  if (!map.value) return
  if (boundaryLayer.value) {
    boundaryLayer.value.remove()
    boundaryLayer.value = null
  }
  if (!showBoundary.value) return
  boundaryLayer.value = L.geoJSON(shaanxiBoundary, {
    style: {
      color: '#47dce9',
      weight: 1.6,
      opacity: 0.88,
      fillColor: '#123d3e',
      fillOpacity: 0.07,
    },
  }).addTo(map.value)
  boundaryLayer.value.bringToBack()
}

const selectTunnel = (tunnel, shouldFly = false) => {
  selectedTunnel.value = tunnel
  boundTunnelId.value = tunnel.id
  selectedHistoryId.value = null
  rightOpen.value = true
  if (window.innerWidth < 900) leftOpen.value = false
  if (shouldFly && map.value) {
    map.value.flyTo([tunnel.latitude, tunnel.longitude], tunnel.sourceCoordinate ? 11 : 9.5, {
      duration: 1.15,
      easeLinearity: 0.22,
    })
  }
  nextTick(drawMarkers)
}

const resetMap = () => {
  if (!map.value) return
  map.value.flyTo([33.82, 108.75], 7, { duration: 1 })
}

const focusFiltered = () => {
  if (!map.value || !filteredTunnels.value.length) return
  const bounds = L.latLngBounds(filteredTunnels.value.map(item => [item.latitude, item.longitude]))
  map.value.fitBounds(bounds, { padding: [120, 120], maxZoom: 9 })
}

const clearFilters = () => {
  searchText.value = ''
  statusFilter.value = 'all'
  routeFilter.value = 'all'
  positionFilter.value = 'all'
}

const beginDiagnosis = () => {
  leftOpen.value = true
  if (window.innerWidth < 900) rightOpen.value = false
  setTimeout(() => document.querySelector('.upload-zone, .upload-card')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80)
}

const quickAction = action => {
  if (action === 'terminal') {
    const tunnel = tunnels.find(item => item.id === 'SX-TUN-0007')
    selectTunnel(tunnel, true)
    chatMessages.value.push({ role: 'assistant', text: `已定位到${tunnel.name}，右侧已展开实体档案。`, time: '刚刚' })
  }
  if (action === 'pending') {
    positionFilter.value = 'linear'
    focusFiltered()
    chatMessages.value.push({ role: 'assistant', text: '已筛选线性参考定位记录。空心节点均为示意位置，需要叠加道路中心线进一步回算。', time: '刚刚' })
  }
  if (action === 'history') {
    bottomOpen.value = true
    chatMessages.value.push({ role: 'assistant', text: `已展开${selectedTunnel.value.name}的检查与病害档案。`, time: '刚刚' })
  }
}

const inspectHistory = record => {
  selectedHistoryId.value = record.id
  leftOpen.value = true
  chatMessages.value.push({ role: 'assistant', text: `已调取记录 ${record.id}：${record.outcome}。`, time: '刚刚' })
}

const selectBore = bore => {
  activeBore.value = bore
  selectedSectionId.value = bore === 'up' ? 'S02' : 'D2'
}

const switchTopModule = module => {
  activeTopModule.value = module
  showFilterMenu.value = false
  showLayerMenu.value = false
  if (module === 'diagnosis') leftOpen.value = true
  if (module === 'models') bottomOpen.value = false
}

const openFilePicker = () => fileInput.value?.click()

const handleFile = event => {
  const file = event.target.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    chatMessages.value.push({ role: 'assistant', text: '当前仅支持JPG、PNG或WebP图片，请重新选择。', time: '刚刚' })
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    chatMessages.value.push({ role: 'assistant', text: '图片超过20MB，请压缩后重新上传。', time: '刚刚' })
    return
  }
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value)
  uploadedFile.value = file
  imagePreview.value = URL.createObjectURL(file)
  diagnosisState.value = 'ready'
  diagnosisResult.value = null
  savedRecord.value = false
  chatMessages.value.push({ role: 'user', text: `已上传检查图片：${file.name}`, time: '刚刚' })
  chatMessages.value.push({ role: 'assistant', text: `图片已通过格式检查。当前关联${currentBoundTunnel.value.name}，确认后即可开始诊断。`, time: '刚刚' })
}

const removeUpload = () => {
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value)
  uploadedFile.value = null
  imagePreview.value = null
  diagnosisState.value = 'idle'
  diagnosisResult.value = null
  if (fileInput.value) fileInput.value.value = ''
}

const delay = ms => new Promise(resolve => setTimeout(resolve, ms))

const buildDiagnosisResult = tunnel => {
  if (tunnel.healthStatus === 'normal') {
    return {
      outcome: 'normal',
      headline: '未发现明确病害',
      summary: '本次影像未检测到超过阈值的裂缝、渗漏水或衬砌剥落区域。建议按常规周期继续巡检。',
      confidence: 94.2,
      grade: 'I类 · 状况良好',
      findings: [],
    }
  }
  if (tunnel.healthStatus === 'uninspected') {
    return {
      outcome: 'review',
      headline: '识别结果需要人工复核',
      summary: '影像局部存在反光与遮挡，模型无法形成稳定结论。建议补拍正视影像或转人工复核。',
      confidence: 63.8,
      grade: '暂不分级',
      findings: [{ type: '疑似渗漏水', confidence: 63.8, measure: '区域约0.42㎡（演示）', location: '拱腰区域' }],
    }
  }
  const urgent = tunnel.healthStatus === 'urgent'
  return {
    outcome: 'disease',
    headline: urgent ? '发现2类病害，建议紧急复核' : '发现2处疑似病害',
    summary: urgent
      ? '裂缝宽度与渗漏范围达到Demo规则库重点阈值，建议24小时内组织人工复核。'
      : '检测到衬砌裂缝与渗漏水区域，建议现场复测后纳入处置计划。',
    confidence: urgent ? 93.6 : 91.6,
    grade: urgent ? 'IV类 · 紧急复核' : 'III类 · 重点处置',
    findings: [
      { type: '衬砌裂缝', confidence: 91.6, measure: '长1.34m / 宽0.82mm（演示）', location: '左拱腰 K0+236' },
      { type: '渗漏水', confidence: 86.4, measure: '影响面积0.67㎡（演示）', location: '拱顶 K0+238' },
    ],
  }
}

const startDiagnosis = async () => {
  if (!uploadedFile.value || diagnosisState.value === 'running') return
  diagnosisState.value = 'running'
  diagnosisStage.value = 0
  diagnosisResult.value = null
  savedRecord.value = false
  const tunnel = currentBoundTunnel.value
  selectTunnel(tunnel, true)
  chatMessages.value.push({ role: 'assistant', text: `已创建诊断任务，地图正在定位${tunnel.name}。`, time: '刚刚' })

  for (let index = 0; index < diagnosisStages.length; index += 1) {
    diagnosisStage.value = index
    await delay(index === 0 ? 700 : 850)
  }
  diagnosisResult.value = buildDiagnosisResult(tunnel)
  diagnosisState.value = 'complete'
  activeResultTab.value = 'result'
  chatMessages.value.push({ role: 'assistant', text: diagnosisResult.value.headline, time: '刚刚' })
  await nextTick()
  document.querySelector('.diagnosis-result')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

const saveRecord = () => {
  if (savedRecord.value || !diagnosisResult.value) return
  const record = {
    id: `AI-${new Date().getFullYear()}-${String(createdRecords.value.length + 1).padStart(3, '0')}`,
    tunnelId: currentBoundTunnel.value.id,
    tunnel: currentBoundTunnel.value.name,
    disease: diagnosisResult.value.findings[0]?.type || 'AI影像检查',
    outcome: diagnosisResult.value.headline,
    date: new Date().toLocaleDateString('zh-CN').replaceAll('/', '-'),
    level: diagnosisResult.value.grade.split(' · ')[0],
    status: diagnosisResult.value.outcome === 'normal' ? '已归档' : '待复核',
  }
  createdRecords.value.unshift(record)
  savedRecord.value = true
  diagnosisState.value = 'saved'
  bottomOpen.value = true
  selectedHistoryId.value = record.id
  chatMessages.value.push({ role: 'assistant', text: `诊断记录 ${record.id} 已进入${currentBoundTunnel.value.name}档案，处置闭环可继续跟踪。`, time: '刚刚' })
}

const restartDiagnosis = () => {
  diagnosisState.value = uploadedFile.value ? 'ready' : 'idle'
  diagnosisResult.value = null
  savedRecord.value = false
  diagnosisStage.value = 0
}

let clockTimer
onMounted(() => {
  const updateClock = () => {
    const now = new Date()
    nowTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
    nowDate.value = now.toLocaleDateString('zh-CN').replaceAll('/', '-')
  }
  updateClock()
  clockTimer = window.setInterval(updateClock, 1000)
  if (window.innerWidth < 900) rightOpen.value = false
  map.value = L.map('map', {
    zoomControl: false,
    attributionControl: true,
    minZoom: 6,
    maxZoom: 14,
    zoomSnap: 0.25,
    preferCanvas: true,
  }).setView([33.82, 108.75], 7)

  if (tiandituToken) {
    const commonOptions = {
      subdomains: '01234567',
      minZoom: 1,
      maxZoom: 18,
      attribution: '<a href="https://www.tianditu.gov.cn/" target="_blank" rel="noreferrer">天地图</a>',
    }
    imageryLayer.value = L.tileLayer(
      `https://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${encodeURIComponent(tiandituToken)}`,
      commonOptions,
    ).addTo(map.value)
    referenceLayer.value = L.tileLayer(
      `https://t{s}.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${encodeURIComponent(tiandituToken)}`,
      { ...commonOptions, opacity: 0.9 },
    ).addTo(map.value)
  } else {
    mapSourceMode.value = 'fallback'
    imageryLayer.value = L.tileLayer('https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/g/{z}/{y}/{x}.jpg', {
      maxZoom: 14,
      crossOrigin: true,
      attribution: '<a href="https://cloudless.eox.at/" target="_blank" rel="noreferrer">EOxCloudless</a> · Copernicus Sentinel data 2025',
    }).addTo(map.value)
    referenceLayer.value = L.tileLayer('https://tiles.maps.eox.at/wmts/1.0.0/overlay/default/g/{z}/{y}/{x}.png', {
      maxZoom: 14,
      crossOrigin: true,
      opacity: 0.78,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map.value)
  }

  roadLayer.value = L.layerGroup().addTo(map.value)
  markerLayer.value = L.layerGroup().addTo(map.value)
  labelLayer.value = L.layerGroup().addTo(map.value)

  cityAnchors.forEach(city => {
    L.marker(city.coordinates, {
      interactive: false,
      icon: L.divIcon({
        className: 'city-label-wrapper',
        html: `<span class="city-label">${escapeHtml(city.name)}</span>`,
        iconSize: [52, 22],
        iconAnchor: [26, 11],
      }),
    }).addTo(map.value)
  })

  drawBoundary()
  drawRoads()
  drawMarkers()
  map.value.on('zoomend', () => {
    mapZoom.value = map.value.getZoom()
    drawMarkers()
  })
  setTimeout(() => map.value?.invalidateSize(), 120)
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value)
  map.value?.remove()
})

watch([filteredTunnels, selectedTunnel], drawMarkers, { deep: true })
watch(showRoads, drawRoads)
watch(showBoundary, drawBoundary)
watch(showReferenceLabels, visible => {
  if (!map.value || !referenceLayer.value) return
  if (visible) referenceLayer.value.addTo(map.value)
  else referenceLayer.value.remove()
})
watch(showTunnels, drawMarkers)
watch(boundTunnelId, id => {
  const tunnel = tunnels.find(item => item.id === id)
  if (tunnel) selectTunnel(tunnel, false)
})
watch(selectedTunnel, () => {
  selectedSectionId.value = activeBore.value === 'up' ? 'S02' : 'D2'
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand-block">
        <div>
          <h1>隧道衬砌病害检测数据的管理平台</h1>
        </div>
      </div>

      <nav class="reference-nav" aria-label="系统模块">
        <button :class="{ active: activeTopModule === 'diagnosis' }" @click="switchTopModule('diagnosis')"><Sparkles :size="16" />智能诊断</button>
        <button :class="{ active: activeTopModule === 'models' }" @click="switchTopModule('models')"><BrainCircuit :size="16" />模型中心</button>
      </nav>

      <div class="top-actions">
        <div class="top-clock"><strong>{{ nowTime }}</strong><span>{{ nowDate }}</span></div>
        <span class="service-state" title="算法服务正常"><i></i></span>
        <div class="avatar">管</div><span class="admin-label">管理员</span><ChevronDown :size="13" />
      </div>
    </header>

    <section class="status-rail" aria-label="全局统计">
      <div class="status-intro">
        <Radar :size="18" />
        <div><strong>陕西省隧道运行态势</strong><span>更新时间 2026-09-04 14:32</span></div>
      </div>
      <div class="stat-item"><Database :size="18" /><span>隧道实体</span><strong>{{ stats.total }}</strong><em>条</em></div>
      <div class="stat-item"><LocateFixed :size="18" /><span>源坐标记录</span><strong>{{ stats.sourceCoordinates }}</strong><em>条</em></div>
      <div class="stat-item stat-warning"><AlertTriangle :size="18" /><span>重点关注</span><strong>{{ stats.concern }}</strong><em>座</em></div>
      <div class="stat-item"><Clock3 :size="18" /><span>待巡检</span><strong>{{ stats.pending }}</strong><em>座</em></div>
      <div class="rail-note"><span>空间数据</span>实线点=源坐标，空心点=线性参考/范围示意</div>
    </section>

    <main class="workspace">
      <div id="map" class="map-canvas" aria-label="陕西省隧道二维地图"></div>
      <div class="map-vignette"></div>
      <div :class="['map-source-banner', mapSourceMeta.state]">
        <Layers3 :size="15" />
        <div><strong>{{ mapSourceMeta.label }}</strong><span>{{ mapSourceMeta.detail }}</span></div>
      </div>

      <section class="map-toolbar" aria-label="地图筛选工具">
        <div class="map-search">
          <Search :size="17" />
          <input v-model="searchText" type="search" placeholder="搜索隧道、路线或行政区" aria-label="搜索隧道" />
          <span>{{ filteredTunnels.length }}/{{ tunnels.length }}</span>
        </div>
        <div class="toolbar-divider"></div>
        <select v-model="routeFilter" aria-label="路线筛选">
          <option value="all">全部路线</option>
          <option v-for="route in routeOptions" :key="route" :value="route">{{ route }}</option>
        </select>
        <button :class="['tool-button', { active: showFilterMenu }]" @click="showFilterMenu = !showFilterMenu"><Filter :size="17" />筛选</button>
        <button class="tool-button" @click="focusFiltered"><Maximize2 :size="17" />适配范围</button>

        <div v-if="showFilterMenu" class="filter-popover">
          <div class="popover-head"><strong>高级筛选</strong><button @click="showFilterMenu = false"><X :size="16" /></button></div>
          <label>运行状态
            <select v-model="statusFilter">
              <option value="all">全部状态</option>
              <option v-for="(meta, key) in statusMeta" :key="key" :value="key">{{ meta.label }}</option>
            </select>
          </label>
          <label>空间赋位
            <select v-model="positionFilter">
              <option value="all">全部定位等级</option>
              <option value="verified">已核验坐标</option>
              <option value="linear">线性参考示意</option>
              <option value="range">范围定位示意</option>
            </select>
          </label>
          <div class="filter-actions"><button @click="clearFilters">重置</button><button class="primary-mini" @click="showFilterMenu = false; focusFiltered()">应用筛选</button></div>
        </div>
      </section>

      <section v-if="activeTopModule === 'models'" class="model-center-panel" aria-label="模型中心">
        <header>
          <div class="model-center-title"><span><BrainCircuit :size="25" /></span><div><small>MODEL SERVICE CENTER</small><h2>模型中心</h2><p>隧道病害识别算法与技术状况分级服务</p></div></div>
          <button aria-label="返回智能诊断" @click="switchTopModule('diagnosis')"><X :size="18" /></button>
        </header>
        <div class="model-kpis"><article><strong>4</strong><span>在线服务</span></article><article><strong>2.8s</strong><span>平均推理耗时</span></article><article><strong>91.2%</strong><span>复核通过率 · Demo</span></article></div>
        <div class="model-service-grid">
          <article v-for="model in modelServices" :key="model.name">
            <div class="model-card-head"><span><BrainCircuit :size="18" /></span><em><i></i>{{ model.state }}</em></div>
            <h3>{{ model.name }}</h3><p>{{ model.scope }}</p>
            <div class="model-card-meta"><span>{{ model.version }}</span><strong>{{ model.metric }}<small>{{ model.label }}</small></strong></div>
          </article>
        </div>
        <footer><ShieldCheck :size="15" /><span>前端通过统一算法适配协议调用模型；当前指标和状态用于交互演示。</span><button @click="switchTopModule('diagnosis')">返回智能诊断</button></footer>
      </section>

      <aside :class="['ai-panel', { collapsed: !leftOpen }]">
        <button v-if="!leftOpen" class="panel-restore left" aria-label="展开AI诊断助手" @click="leftOpen = true"><Bot :size="21" /><ChevronRight :size="15" /></button>
        <template v-else>
          <header class="panel-header">
            <div class="panel-title-icon doctor-avatar"><img src="/tunnel-doctor-avatar.png" alt="隧道病害医生头像" /></div>
            <div><h2>秦隧质检助手</h2><p><span></span>4项识别算法已就绪</p></div>
            <button class="panel-close" aria-label="收起AI诊断助手" @click="leftOpen = false"><PanelLeftClose :size="19" /></button>
          </header>

          <div class="assistant-body">
            <div class="message-stream">
              <div v-for="(message, index) in chatMessages" :key="index" :class="['message-row', message.role]">
                <div v-if="message.role === 'assistant'" class="message-avatar"><img src="/tunnel-doctor-avatar.png" alt="" /></div>
                <div class="message-bubble"><p>{{ message.text }}</p><time>{{ message.time }}</time></div>
              </div>
            </div>

            <div v-if="diagnosisState === 'idle'" class="quick-actions">
              <button @click="quickAction('terminal')"><LocateFixed :size="15" />定位终南山隧道</button>
              <button @click="quickAction('pending')"><Route :size="15" />查看线性参考记录</button>
              <button @click="quickAction('history')"><History :size="15" />查询历史病害</button>
            </div>

            <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="handleFile" />
            <button v-if="!uploadedFile" class="upload-zone" @click="openFilePicker">
              <span class="upload-icon"><UploadCloud :size="24" /></span>
              <strong>上传隧道检查图片</strong>
              <small>支持 JPG、PNG、WebP，单张不超过20MB</small>
              <em>选择图片</em>
            </button>

            <section v-else class="upload-card">
              <div class="image-preview-wrap">
                <img :src="imagePreview" alt="已上传的隧道检查图片" />
                <div v-if="diagnosisState === 'running'" class="scan-effect"><span></span></div>
                <svg v-if="diagnosisResult?.outcome === 'disease'" class="detection-overlay" viewBox="0 0 100 64" preserveAspectRatio="none" aria-hidden="true">
                  <rect x="16" y="12" width="31" height="39" rx="2" class="box crack-box" />
                  <path d="M24 17 C27 24, 22 27, 31 34 S29 44, 39 49" class="crack-path" />
                  <rect x="57" y="9" width="28" height="29" rx="2" class="box water-box" />
                </svg>
                <div v-if="diagnosisResult?.outcome === 'normal'" class="normal-overlay"><CheckCircle2 :size="30" /><span>未发现明确病害</span></div>
                <button class="remove-image" aria-label="移除图片" @click="removeUpload"><X :size="15" /></button>
              </div>
              <div class="file-meta"><FileImage :size="18" /><div><strong>{{ uploadedFile.name }}</strong><span>{{ (uploadedFile.size / 1024 / 1024).toFixed(2) }} MB · 本地演示，不上传服务器</span></div></div>
            </section>

            <section v-if="uploadedFile" class="binding-card">
              <div class="binding-head"><span><MapPin :size="16" />关联隧道</span><em :class="`position-${currentBoundTunnel.positionType}`">{{ positionMeta[currentBoundTunnel.positionType].label }}</em></div>
              <select v-model="boundTunnelId" aria-label="选择关联隧道">
                <option v-for="tunnel in tunnels" :key="tunnel.id" :value="tunnel.id">{{ tunnel.name }} · {{ tunnel.routeCode }}</option>
              </select>
              <p>{{ currentBoundTunnel.positionDescription || currentBoundTunnel.administrativeLocation }}</p>
            </section>

            <section v-if="diagnosisState === 'running'" class="diagnosis-progress">
              <div class="progress-head"><span><Activity :size="16" />AI正在诊断</span><strong>{{ Math.round(((diagnosisStage + 1) / diagnosisStages.length) * 100) }}%</strong></div>
              <div class="progress-track"><span :style="{ width: `${((diagnosisStage + 1) / diagnosisStages.length) * 100}%` }"></span></div>
              <div v-for="(stage, index) in diagnosisStages" :key="stage.label" :class="['stage-row', { done: index < diagnosisStage, active: index === diagnosisStage }]">
                <span class="stage-dot"><CheckCircle2 v-if="index < diagnosisStage" :size="15" /><i v-else></i></span>
                <div><strong>{{ stage.label }}</strong><small>{{ stage.detail }}</small></div>
              </div>
            </section>

            <section v-if="diagnosisResult" :class="['diagnosis-result', `result-${diagnosisResult.outcome}`]">
              <header>
                <span class="result-icon">
                  <CheckCircle2 v-if="diagnosisResult.outcome === 'normal'" :size="21" />
                  <AlertTriangle v-else-if="diagnosisResult.outcome === 'disease'" :size="21" />
                  <UserRoundCheck v-else :size="21" />
                </span>
                <div><strong>{{ diagnosisResult.headline }}</strong><small>综合置信度 {{ diagnosisResult.confidence }}%</small></div>
                <em>{{ diagnosisResult.grade }}</em>
              </header>
              <div class="result-tabs">
                <button :class="{ active: activeResultTab === 'result' }" @click="activeResultTab = 'result'">识别结果</button>
                <button :class="{ active: activeResultTab === 'basis' }" @click="activeResultTab = 'basis'">分级依据</button>
                <button :class="{ active: activeResultTab === 'action' }" @click="activeResultTab = 'action'">处置建议</button>
              </div>
              <div v-if="activeResultTab === 'result'" class="result-content">
                <p>{{ diagnosisResult.summary }}</p>
                <article v-for="finding in diagnosisResult.findings" :key="finding.type" class="finding-card">
                  <div><strong>{{ finding.type }}</strong><em>{{ finding.confidence }}%</em></div>
                  <span>{{ finding.location }}</span><span>{{ finding.measure }}</span>
                </article>
                <div v-if="!diagnosisResult.findings.length" class="empty-finding"><ShieldCheck :size="22" />当前图片无需要列出的病害实例</div>
              </div>
              <div v-else-if="activeResultTab === 'basis'" class="result-content evidence-list">
                <p>分级结果由识别置信度、几何量化指标、病害位置和规则阈值综合计算。</p>
                <span><i></i>规则库：公路隧道技术状况评定规则（Demo配置）</span>
                <span><i></i>置信度不等于病害等级；低置信度结果转人工复核</span>
                <span><i></i>无比例尺图片的毫米级测量值仅用于交互演示</span>
              </div>
              <div v-else class="result-content action-list">
                <div><strong>24小时内</strong><span>人工复核影像与病害位置</span></div>
                <div><strong>7日内</strong><span>现场复测裂缝宽度与渗漏范围</span></div>
                <div><strong>30日内</strong><span>根据复核结论制定维修及跟踪计划</span></div>
              </div>
              <div class="result-actions">
                <button @click="restartDiagnosis"><RotateCcw :size="15" />重新识别</button>
                <button class="primary" :disabled="savedRecord" @click="saveRecord"><FileCheck2 :size="15" />{{ savedRecord ? '已进入档案' : '形成诊断记录' }}</button>
              </div>
            </section>
          </div>

          <footer v-if="uploadedFile && ['ready', 'idle'].includes(diagnosisState)" class="diagnosis-footer">
            <div><ShieldCheck :size="15" />诊断结果需经专业人员复核</div>
            <button class="run-button" @click="startDiagnosis"><Play :size="16" fill="currentColor" />开始AI诊断</button>
          </footer>
        </template>
      </aside>

      <aside :class="['detail-panel', { collapsed: !rightOpen }]">
        <button v-if="!rightOpen" class="panel-restore right" aria-label="展开隧道信息" @click="rightOpen = true"><ChevronLeft :size="15" /><Database :size="20" /></button>
        <template v-else>
          <header class="detail-header">
            <div>
              <span class="eyebrow">隧道地理实体 · {{ selectedTunnel.id }}</span>
              <h2>{{ selectedTunnel.name }}</h2>
              <p>{{ selectedTunnel.alias || selectedTunnel.routeSection || selectedTunnel.road }}</p>
            </div>
            <button class="panel-close" aria-label="收起隧道信息" @click="rightOpen = false"><ChevronRight :size="19" /></button>
          </header>

          <div class="detail-scroll">
            <section class="health-overview">
              <div class="score-ring" :style="{ '--score-color': statusMeta[selectedTunnel.healthStatus].color, '--score': selectedTunnel.healthScore || 0 }">
                <div><strong>{{ selectedTunnel.healthScore ?? '—' }}</strong><span>健康指数</span></div>
              </div>
              <div class="health-copy">
                <span class="health-badge" :style="{ color: statusMeta[selectedTunnel.healthStatus].color, borderColor: `${statusMeta[selectedTunnel.healthStatus].color}55`, background: `${statusMeta[selectedTunnel.healthStatus].color}16` }">{{ statusMeta[selectedTunnel.healthStatus].label }} · 演示</span>
                <strong>{{ statusMeta[selectedTunnel.healthStatus].level }}技术状况</strong>
                <p>最近巡检 {{ selectedTunnel.lastInspection || '暂无记录' }} · 病害 {{ selectedTunnel.defectCount }} 项</p>
              </div>
            </section>

            <section class="detail-section">
              <div class="section-heading"><strong>基础信息</strong><span>来源属性</span></div>
              <div class="property-grid">
                <div><span>所属道路</span><strong>{{ selectedTunnel.road }}</strong></div>
                <div><span>路线编号</span><strong>{{ selectedTunnel.routeCode }}</strong></div>
                <div><span>行政区</span><strong>{{ selectedTunnel.city }} {{ selectedTunnel.county !== '待补' ? selectedTunnel.county : '' }}</strong></div>
                <div><span>隧道长度</span><strong>{{ selectedLength }}</strong></div>
                <div><span>隧道等级</span><strong>{{ selectedTunnel.level }}</strong></div>
                <div><span>通车年份</span><strong>{{ selectedTunnel.opened || '待补' }}</strong></div>
              </div>
              <div class="wide-property"><span>管养单位</span><strong>{{ selectedTunnel.maintenance }}</strong></div>
            </section>

            <section class="detail-section spatial-section">
              <div class="section-heading"><strong>空间赋位</strong><span :class="`position-pill ${selectedTunnel.positionType}`">{{ selectedTunnel.spatialGrade }}</span></div>
              <div class="coordinate-row"><LocateFixed :size="17" /><div><strong>{{ selectedTunnel.longitude.toFixed(6) }}, {{ selectedTunnel.latitude.toFixed(6) }}</strong><span>{{ selectedTunnel.sourceCoordinate ? '来源数据坐标' : '仅用于Demo地图展示的示意坐标' }}</span></div></div>
              <p>{{ selectedTunnel.positionDescription || selectedTunnel.administrativeLocation }}</p>
              <div v-if="!selectedTunnel.sourceCoordinate" class="accuracy-warning"><AlertTriangle :size="15" /><span>需叠加道路中心线和里程桩进一步校准，不能作为洞口测量坐标使用。</span></div>
            </section>

            <section class="detail-section assessment-section">
              <div class="section-heading"><strong>技术状况评定链</strong><span>报告口径 · Demo</span></div>
              <div class="assessment-chain">
                <span><b>AI置信度</b><em>证据可信度</em></span><i></i>
                <span><b>病害状况值</b><em>类型与规模</em></span><i></i>
                <span><b>构件评分</b><em>分段汇总</em></span><i></i>
                <span><b>JGCI</b><em>总体指数</em></span>
              </div>
              <p class="assessment-note">模型结论、人工复核、处置结果和年度复检分别留痕；识别置信度不直接等同于技术状况等级。</p>
            </section>

            <section class="detail-section">
              <div class="section-heading"><strong>最近病害</strong><button @click="bottomOpen = true">查看全部</button></div>
              <div v-if="selectedTunnel.defectCount" class="disease-list">
                <article><span class="disease-mark warning"><Zap :size="15" /></span><div><strong>衬砌裂缝</strong><p>左拱腰 · 待人工复核</p></div><em>III类</em></article>
                <article><span class="disease-mark attention"><Activity :size="15" /></span><div><strong>渗漏水</strong><p>拱顶 · 持续监测</p></div><em>II类</em></article>
              </div>
              <div v-else class="no-disease"><ShieldCheck :size="20" /><span>暂无病害记录</span></div>
            </section>
          </div>

          <footer class="detail-actions">
            <button @click="bottomOpen = true"><Eye :size="16" />查看完整档案</button>
            <button class="primary" @click="beginDiagnosis"><Sparkles :size="16" />从该隧道发起诊断</button>
          </footer>
        </template>
      </aside>

      <div class="map-controls">
        <button aria-label="放大地图" @click="map?.zoomIn()"><ZoomIn :size="18" /></button>
        <button aria-label="缩小地图" @click="map?.zoomOut()"><ZoomOut :size="18" /></button>
        <button aria-label="复位地图" @click="resetMap"><LocateFixed :size="18" /></button>
        <button :class="{ active: showLayerMenu }" aria-label="图层控制" @click="showLayerMenu = !showLayerMenu"><Layers3 :size="18" /></button>
        <div v-if="showLayerMenu" class="layer-popover">
          <strong>二维影像图层</strong>
          <label><span><Layers3 :size="15" />地名与边界注记</span><input v-model="showReferenceLabels" type="checkbox" /></label>
          <label><span><Network :size="15" />交通路网</span><input v-model="showRoads" type="checkbox" /></label>
          <label><span><MapPin :size="15" />隧道实体</span><input v-model="showTunnels" type="checkbox" /></label>
          <label><span><Maximize2 :size="15" />行政边界</span><input v-model="showBoundary" type="checkbox" /></label>
        </div>
      </div>

      <section class="map-legend">
        <strong>运行状态 <small>{{ mapSourceMeta.label }}</small></strong>
        <div><span v-for="(meta, key) in statusMeta" :key="key"><i :style="{ background: meta.color }"></i>{{ meta.short }}</span></div>
        <div class="position-legend"><span><i class="solid-dot"></i>源坐标</span><span><i class="hollow-dot"></i>线性参考/范围示意</span></div>
      </section>

      <section :class="['history-dock', { open: bottomOpen }]" aria-label="当前隧道检查记录">
        <button class="dock-handle" @click="bottomOpen = !bottomOpen">
          <History :size="15" /><span>{{ selectedTunnel.name }} · 检查与病害记录</span><em>{{ selectedHistoryRows.length }} 条</em><ChevronDown :class="{ rotated: bottomOpen }" :size="15" />
        </button>
        <div v-if="bottomOpen" class="dock-content">
          <header><div><span>TUNNEL CONDITION LEDGER</span><strong>{{ selectedTunnel.name }}衬砌病害档案</strong></div><p>按“方向—分段—构件—病害—证据—处置”组织，地图与当前对象同步。</p></header>
          <div class="dock-layout">
            <section class="linear-profile" aria-label="隧道衬砌二维展开图">
              <div class="linear-head">
                <div class="bore-switch"><button :class="{ active: activeBore === 'up' }" @click="selectBore('up')">上行洞</button><button :class="{ active: activeBore === 'down' }" @click="selectBore('down')">下行洞</button></div>
                <span>{{ tunnelLinearProfile.coordinateNote }}</span>
              </div>
              <div class="lining-strip">
                <button v-for="section in tunnelLinearProfile.sections" :key="section.id" :class="[`state-${section.state}`, { active: selectedLinearSection.id === section.id }]" @click="selectedSectionId = section.id">
                  <span class="section-top"><b>{{ section.id }}</b><em>{{ section.score ?? '—' }}</em></span>
                  <span class="lining-surface">
                    <i v-for="defect in section.defects" :key="`${defect.type}-${defect.part}`" :class="`geometry-${defect.geometry}`" :title="`${defect.type} · ${defect.part}`"></i>
                  </span>
                  <small>{{ section.range }}</small>
                </button>
              </div>
              <div class="section-inspector">
                <div><span>当前分段</span><strong>{{ selectedLinearSection.range }}</strong></div>
                <div><span>构件评分</span><strong>{{ selectedLinearSection.score ?? '未检查' }}</strong></div>
                <div class="section-defects"><span>病害实例</span><p v-if="selectedLinearSection.defects.length"><em v-for="defect in selectedLinearSection.defects" :key="defect.type">{{ defect.type }} · {{ defect.part }} · {{ defect.lifecycle }}</em></p><strong v-else>暂无明确病害</strong></div>
              </div>
            </section>
            <div class="record-list">
              <button v-for="record in selectedHistoryRows" :key="record.id" :class="{ active: selectedHistoryId === record.id }" @click="inspectHistory(record)">
                <span class="record-date">{{ record.date }}</span><i></i><div><strong>{{ record.disease }}</strong><p>{{ record.outcome }}</p><small>{{ record.id }}</small></div><em :class="record.level === 'I类' ? 'ok' : 'risk'">{{ record.level }}</em><b>{{ record.status }}</b>
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>
