<template>
  <div class="p-6 max-w-[1400px] mx-auto space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="space-y-1">
        <h1 class="text-3xl font-bold tracking-tight text-foreground">扫描管理</h1>
        <p class="text-muted-foreground">资产管理、扫描任务调度与漏洞发现</p>
      </div>
    </div>

    <!-- Tabs -->
    <Tabs v-model="activeTab" class="space-y-4">
      <TabsList class="bg-muted/50">
        <TabsTrigger value="assets" class="gap-2">
          <Target class="size-4" />
          资产管理
          <Badge v-if="assetTotal > 0" variant="secondary" class="ml-1 h-5 px-1.5 text-xs">{{ assetTotal }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="tasks" class="gap-2">
          <Shield class="size-4" />
          扫描任务
          <Badge v-if="taskTotal > 0" variant="secondary" class="ml-1 h-5 px-1.5 text-xs">{{ taskTotal }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="findings" class="gap-2">
          <Bug class="size-4" />
          漏洞发现
          <Badge v-if="findingTotal > 0" variant="secondary" class="ml-1 h-5 px-1.5 text-xs">{{ findingTotal }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="nmap-hosts" class="gap-2">
          <Monitor class="size-4" />
          Nmap 主机
          <Badge v-if="nmapHostTotal > 0" variant="secondary" class="ml-1 h-5 px-1.5 text-xs">{{ nmapHostTotal }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="discovered-assets" class="gap-2">
          <Scan class="size-4" />
          发现资产
          <Badge v-if="discoveredTotal > 0" variant="secondary" class="ml-1 h-5 px-1.5 text-xs">{{ discoveredTotal }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="fix-tickets" class="gap-2">
          <Wrench class="size-4" />
          修复工单
          <Badge v-if="ticketTotal > 0" variant="secondary" class="ml-1 h-5 px-1.5 text-xs">{{ ticketTotal }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="attack-path" class="gap-2">
          <Route class="size-4" />
          攻击路径
        </TabsTrigger>
      </TabsList>

      <!-- ===== Tab: 资产管理 ===== -->
      <TabsContent value="assets" class="space-y-4">
        <!-- Asset Toolbar -->
        <div class="flex items-center gap-3 flex-wrap">
          <div class="relative flex-1 min-w-[200px]">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input v-model="assetKeyword" placeholder="搜索目标..." class="pl-9" @keyup.enter="loadAssets(1)" />
          </div>
          <div class="flex gap-1">
            <Button
              v-for="t in ['', 'IP', 'CIDR', 'DOMAIN']"
              :key="t"
              :variant="assetTypeFilter === t ? 'default' : 'outline'"
              size="sm"
              class="cursor-pointer"
              @click="assetTypeFilter = t; loadAssets(1)"
            >
              {{ t || '全部' }}
            </Button>
          </div>
          <Dialog v-model:open="showCreateAsset">
            <DialogTrigger as-child>
              <Button class="cursor-pointer gap-2">
                <Plus class="size-4" />
                添加资产
              </Button>
            </DialogTrigger>
            <DialogContent class="sm:max-w-[440px]">
              <DialogHeader>
                <DialogTitle>添加扫描资产</DialogTitle>
                <DialogDescription>添加需要定期扫描的目标（IP/CIDR/域名）</DialogDescription>
              </DialogHeader>
              <div class="space-y-4 pt-2">
                <div class="space-y-2">
                  <Label>目标</Label>
                  <Input v-model="newAsset.target" placeholder="192.168.1.1 / 10.0.0.0/24 / example.com" />
                </div>
                <div class="space-y-2">
                  <Label>类型</Label>
                  <Select v-model="newAsset.target_type">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="IP">IP 地址</SelectItem>
                      <SelectItem value="CIDR">CIDR 网段</SelectItem>
                      <SelectItem value="DOMAIN">域名</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div class="space-y-2">
                  <Label>标签（逗号分隔，选填）</Label>
                  <Input v-model="newAsset.tags" placeholder="内网,核心,web" />
                </div>
                <div class="space-y-2">
                  <Label>描述（选填）</Label>
                  <Input v-model="newAsset.description" placeholder="资产说明" />
                </div>
                <p v-if="assetError" class="text-sm text-destructive">{{ assetError }}</p>
              </div>
              <DialogFooter>
                <Button variant="outline" class="cursor-pointer" @click="showCreateAsset = false">取消</Button>
                <Button class="cursor-pointer" :disabled="assetLoading" @click="createAsset">
                  {{ assetLoading ? '创建中...' : '创建' }}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <!-- Asset Table -->
        <div class="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow class="bg-muted/30">
                <TableHead>目标</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>标签</TableHead>
                <TableHead>优先级</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead class="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="assetLoading">
                <TableCell colspan="7" class="text-center py-10 text-muted-foreground">加载中...</TableCell>
              </TableRow>
              <TableRow v-else-if="assets.length === 0">
                <TableCell colspan="7" class="text-center py-10">
                  <div class="flex flex-col items-center gap-2 text-muted-foreground">
                    <Target class="size-10 opacity-30" />
                    <span class="text-sm">暂无资产</span>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-for="asset in assets" :key="asset.id" class="hover:bg-muted/20">
                <TableCell class="font-mono text-sm font-medium">{{ asset.target }}</TableCell>
                <TableCell>
                  <Badge variant="outline" class="text-xs">{{ asset.target_type }}</Badge>
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">{{ asset.tags || '—' }}</TableCell>
                <TableCell class="text-sm">{{ asset.priority }}</TableCell>
                <TableCell>
                  <Badge :class="asset.enabled ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-muted text-muted-foreground'">
                    {{ asset.enabled ? '启用' : '禁用' }}
                  </Badge>
                </TableCell>
                <TableCell class="text-xs text-muted-foreground">{{ formatTime(asset.created_at) }}</TableCell>
                <TableCell class="text-right">
                  <div class="flex items-center justify-end gap-2">
                    <Button variant="ghost" size="sm" class="cursor-pointer h-7 text-xs" @click="toggleAsset(asset)">
                      {{ asset.enabled ? '禁用' : '启用' }}
                    </Button>
                    <Button variant="ghost" size="sm" class="cursor-pointer h-7 text-destructive hover:text-destructive" @click="confirmDeleteAsset(asset)">
                      <Trash2 class="size-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <!-- Asset Pagination -->
        <div v-if="assetTotal > 20" class="flex items-center justify-between text-sm text-muted-foreground">
          <span>共 {{ assetTotal }} 条</span>
          <div class="flex gap-1">
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="assetPage <= 1" @click="loadAssets(assetPage - 1)">
              <ChevronLeft class="size-4" />
            </Button>
            <span class="px-3 py-1 text-xs">第 {{ assetPage }} 页</span>
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="assetPage * 20 >= assetTotal" @click="loadAssets(assetPage + 1)">
              <ChevronRight class="size-4" />
            </Button>
          </div>
        </div>
      </TabsContent>

      <!-- ===== Tab: 扫描任务 ===== -->
      <TabsContent value="tasks" class="space-y-4">
        <!-- Task Toolbar -->
        <div class="flex items-center gap-3 flex-wrap">
          <div class="flex gap-1 flex-wrap">
            <Button
              v-for="s in taskStateOptions"
              :key="s.value"
              :variant="taskStateFilter === s.value ? 'default' : 'outline'"
              size="sm"
              class="cursor-pointer"
              @click="taskStateFilter = s.value; loadTasks(1)"
            >
              {{ s.label }}
            </Button>
          </div>
          <Button variant="outline" size="sm" class="cursor-pointer gap-1 ml-auto" @click="loadTasks(taskPage)">
            <RefreshCw class="size-3.5" />
            刷新
          </Button>
          <Dialog v-model:open="showCreateTask">
            <DialogTrigger as-child>
              <Button class="cursor-pointer gap-2">
                <Plus class="size-4" />
                新建扫描
              </Button>
            </DialogTrigger>
            <DialogContent class="sm:max-w-[480px]">
              <DialogHeader>
                <DialogTitle>新建扫描任务</DialogTitle>
                <DialogDescription>输入目标地址并选择扫描配置</DialogDescription>
              </DialogHeader>
              <div class="space-y-4 pt-2">
                <div class="space-y-2">
                  <Label>目标地址 <span class="text-destructive">*</span></Label>
                  <Input v-model="newTask.target" placeholder="192.168.1.1 / 10.0.0.0/24" />
                </div>
                <div class="space-y-2">
                  <Label>扫描配置</Label>
                  <Select v-model="newTask.profile">
                    <SelectTrigger><SelectValue placeholder="选择扫描配置" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem v-for="p in availableProfiles" :key="p.key" :value="p.key" :disabled="!p.available">
                        <div class="flex flex-col">
                          <span>{{ p.name }}</span>
                          <span class="text-xs text-muted-foreground">{{ p.description }}</span>
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <p v-if="selectedProfile" class="text-xs text-muted-foreground">
                    预计耗时: {{ Math.round(selectedProfile.estimated_seconds / 60) }} 分钟
                  </p>
                </div>
                <div class="space-y-2">
                  <Label>关联资产（选填）</Label>
                  <Select v-model="newTask.asset_id_str">
                    <SelectTrigger><SelectValue placeholder="不关联资产" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">不关联资产</SelectItem>
                      <SelectItem v-for="a in assets" :key="a.id" :value="String(a.id)">
                        {{ a.target }} ({{ a.target_type }})
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <p v-if="taskError" class="text-sm text-destructive">{{ taskError }}</p>
              </div>
              <DialogFooter>
                <Button variant="outline" class="cursor-pointer" @click="showCreateTask = false">取消</Button>
                <Button class="cursor-pointer" :disabled="taskLoading || !newTask.target" @click="createTask">
                  {{ taskLoading ? '创建中...' : '创建任务' }}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <!-- Task Table -->
        <div class="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow class="bg-muted/30">
                <TableHead class="w-16">#ID</TableHead>
                <TableHead>目标</TableHead>
                <TableHead>配置</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>开始时间</TableHead>
                <TableHead>耗时</TableHead>
                <TableHead class="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="taskLoading">
                <TableCell colspan="7" class="text-center py-10 text-muted-foreground">加载中...</TableCell>
              </TableRow>
              <TableRow v-else-if="tasks.length === 0">
                <TableCell colspan="7" class="text-center py-10">
                  <div class="flex flex-col items-center gap-2 text-muted-foreground">
                    <Shield class="size-10 opacity-30" />
                    <span class="text-sm">暂无扫描任务</span>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-for="task in tasks" :key="task.id" class="hover:bg-muted/20">
                <TableCell class="text-xs text-muted-foreground font-mono">#{{ task.id }}</TableCell>
                <TableCell class="font-mono text-sm font-medium">{{ task.target }}</TableCell>
                <TableCell>
                  <Badge variant="outline" class="text-xs">{{ task.profile || 'default' }}</Badge>
                </TableCell>
                <TableCell>
                  <Badge :class="getStateColor(task.state)">{{ getStateLabel(task.state) }}</Badge>
                </TableCell>
                <TableCell class="text-xs text-muted-foreground">{{ task.started_at ? formatTime(task.started_at) : '—' }}</TableCell>
                <TableCell class="text-xs text-muted-foreground">{{ calcDuration(task.started_at, task.ended_at) }}</TableCell>
                <TableCell class="text-right">
                  <div class="flex items-center justify-end gap-2">
                    <Button variant="ghost" size="sm" class="cursor-pointer h-7 gap-1 text-xs" @click="openTaskDetail(task.id)">
                      <Eye class="size-3.5" />
                      详情
                    </Button>
                    <Button
                      v-if="['CREATED','DISPATCHED','RUNNING'].includes(task.state)"
                      variant="ghost"
                      size="sm"
                      class="cursor-pointer h-7 text-xs text-destructive hover:text-destructive"
                      @click="cancelTask(task.id)"
                    >
                      取消
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <!-- Task Pagination -->
        <div v-if="taskTotal > 20" class="flex items-center justify-between text-sm text-muted-foreground">
          <span>共 {{ taskTotal }} 条</span>
          <div class="flex gap-1">
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="taskPage <= 1" @click="loadTasks(taskPage - 1)">
              <ChevronLeft class="size-4" />
            </Button>
            <span class="px-3 py-1 text-xs">第 {{ taskPage }} 页</span>
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="taskPage * 20 >= taskTotal" @click="loadTasks(taskPage + 1)">
              <ChevronRight class="size-4" />
            </Button>
          </div>
        </div>
      </TabsContent>

      <!-- ===== Tab: 漏洞发现 ===== -->
      <TabsContent value="findings" class="space-y-4">
        <!-- 漏洞统计卡片 -->
        <div class="grid gap-3 md:grid-cols-4">
          <Card class="border-red-500/20">
            <CardContent class="pt-4 pb-3">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-xs text-muted-foreground">存在漏洞</p>
                  <p class="text-2xl font-bold text-red-400 mt-0.5">{{ vulnStats != null ? (vulnStats.high ?? 0) + (vulnStats.medium ?? 0) + (vulnStats.low ?? 0) : '—' }}</p>
                </div>
                <AlertTriangle class="size-6 text-red-400/50" />
              </div>
            </CardContent>
          </Card>
          <Card class="border-emerald-500/20">
            <CardContent class="pt-4 pb-3">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-xs text-muted-foreground">已确认安全</p>
                  <p class="text-2xl font-bold text-emerald-400 mt-0.5">{{ vulnStats?.confirmed ?? '—' }}</p>
                </div>
                <ShieldCheck class="size-6 text-emerald-400/50" />
              </div>
            </CardContent>
          </Card>
          <Card class="border-amber-500/20">
            <CardContent class="pt-4 pb-3">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-xs text-muted-foreground">受影响设备</p>
                  <p class="text-2xl font-bold text-amber-400 mt-0.5">{{ vulnStats?.affected_assets ?? '—' }}</p>
                </div>
                <Monitor class="size-6 text-amber-400/50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent class="pt-4 pb-3">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-xs text-muted-foreground">扫描失败</p>
                  <p class="text-2xl font-bold text-muted-foreground mt-0.5">{{ vulnStats?.false_positive ?? '—' }}</p>
                </div>
                <AlertTriangle class="size-6 text-muted-foreground/40" />
              </div>
            </CardContent>
          </Card>
        </div>

        <!-- Findings Toolbar -->
        <div class="flex items-center gap-3 flex-wrap">
          <div class="flex gap-1">
            <Button
              v-for="s in findingSeverityOptions"
              :key="s.value"
              :variant="findingSeverityFilter === s.value ? 'default' : 'outline'"
              size="sm"
              class="cursor-pointer"
              @click="findingSeverityFilter = s.value; loadFindings(1)"
            >
              {{ s.label }}
            </Button>
          </div>
          <div class="flex gap-1 ml-2">
            <Button
              v-for="s in findingStatusOptions"
              :key="s.value"
              :variant="findingStatusFilter === s.value ? 'default' : 'outline'"
              size="sm"
              class="cursor-pointer text-xs"
              @click="findingStatusFilter = s.value; loadFindings(1)"
            >
              {{ s.label }}
            </Button>
          </div>
          <Button variant="outline" size="sm" class="cursor-pointer gap-1 ml-auto" @click="loadFindings(findingPage)">
            <RefreshCw class="size-3.5" />
            刷新
          </Button>
          <Button
            size="sm"
            class="cursor-pointer gap-1.5"
            :disabled="vulnScanning"
            @click="triggerVulnScan"
          >
            <Scan class="size-3.5" :class="vulnScanning ? 'animate-pulse' : ''" />
            {{ vulnScanning ? '扫描中…' : '立即漏洞扫描' }}
          </Button>
        </div>

        <!-- Findings Table -->
        <div class="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow class="bg-muted/30">
                <TableHead>资产</TableHead>
                <TableHead>端口/服务</TableHead>
                <TableHead>严重程度</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>CVE</TableHead>
                <TableHead>证据摘要</TableHead>
                <TableHead>发现时间</TableHead>
                <TableHead class="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="findingLoading">
                <TableCell colspan="8" class="text-center py-10 text-muted-foreground">加载中...</TableCell>
              </TableRow>
              <TableRow v-else-if="findings.length === 0">
                <TableCell colspan="8" class="text-center py-10">
                  <div class="flex flex-col items-center gap-2 text-muted-foreground">
                    <Bug class="size-10 opacity-30" />
                    <span class="text-sm">暂无发现项</span>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-for="f in findings" :key="f.id" class="hover:bg-muted/20">
                <TableCell class="font-mono text-sm">{{ f.asset }}</TableCell>
                <TableCell class="text-sm">
                  <span v-if="f.port">{{ f.port }}/{{ f.service || '?' }}</span>
                  <span v-else class="text-muted-foreground">—</span>
                </TableCell>
                <TableCell>
                  <Badge :class="getSeverityColor(f.severity)">{{ f.severity }}</Badge>
                </TableCell>
                <TableCell>
                  <Select :model-value="f.status" @update:model-value="(v) => updateFindingStatus(f.id, v as string)">
                    <SelectTrigger class="h-7 w-[120px] text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem v-for="s in findingStatusUpdateOptions" :key="s" :value="s" class="text-xs">{{ s }}</SelectItem>
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell class="text-xs text-muted-foreground font-mono">{{ f.cve || '—' }}</TableCell>
                <TableCell class="text-xs text-muted-foreground max-w-[200px] truncate">{{ f.evidence || '—' }}</TableCell>
                <TableCell class="text-xs text-muted-foreground">{{ formatTime(f.created_at) }}</TableCell>
                <TableCell class="text-right">
                  <Button variant="ghost" size="sm" class="cursor-pointer h-7 gap-1 text-xs" @click="openFindingDetail(f)">
                    <Eye class="size-3.5" />
                    查看
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <!-- Findings Pagination -->
        <div v-if="findingTotal > 20" class="flex items-center justify-between text-sm text-muted-foreground">
          <span>共 {{ findingTotal }} 条</span>
          <div class="flex gap-1">
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="findingPage <= 1" @click="loadFindings(findingPage - 1)">
              <ChevronLeft class="size-4" />
            </Button>
            <span class="px-3 py-1 text-xs">第 {{ findingPage }} 页</span>
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="findingPage * 20 >= findingTotal" @click="loadFindings(findingPage + 1)">
              <ChevronRight class="size-4" />
            </Button>
          </div>
        </div>
      </TabsContent>

      <!-- ===== Tab: Nmap 主机 ===== -->
      <TabsContent value="nmap-hosts" class="space-y-4">
        <!-- Toolbar -->
        <div class="flex items-center gap-3 flex-wrap">
          <!-- 扫描历史选择 -->
          <select
            v-model="selectedScanId"
            class="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
            @change="loadNmapHosts()"
          >
            <option value="">最新扫描</option>
            <option v-for="scan in nmapScans" :key="scan.id" :value="scan.id">
              #{{ scan.id }} - {{ scan.target }} [{{ scan.state }}] {{ scan.created_at?.slice(0, 10) ?? '' }}
            </option>
          </select>

          <!-- 状态筛选 -->
          <div class="flex gap-1">
            <Button
              v-for="s in [{ v: '', l: '全部' }, { v: 'up', l: '在线' }, { v: 'down', l: '离线' }]"
              :key="s.v"
              :variant="nmapStateFilter === s.v ? 'default' : 'outline'"
              size="sm"
              class="cursor-pointer"
              @click="nmapStateFilter = s.v; loadNmapHosts()"
            >
              {{ s.l }}
            </Button>
          </div>

          <Button variant="outline" size="sm" class="cursor-pointer gap-1 ml-auto" :disabled="nmapHostLoading" @click="loadNmapHosts()">
            <RefreshCw class="size-3.5" :class="nmapHostLoading ? 'animate-spin' : ''" />
            刷新
          </Button>
          <Button
            variant="outline"
            size="sm"
            class="cursor-pointer gap-1.5"
            @click="openNmapConfigDialog"
          >
            <SettingsIcon class="size-3.5" />
            配置
          </Button>
          <Button
            size="sm"
            class="cursor-pointer gap-1.5"
            :disabled="nmapScanning"
            @click="triggerNmapScan"
          >
            <Scan class="size-3.5" :class="nmapScanning ? 'animate-pulse' : ''" />
            {{ nmapScanning ? '扫描中…' : '立即扫描' }}
          </Button>
        </div>

        <!-- Nmap 统计 -->
        <div v-if="nmapStats" class="grid gap-3 md:grid-cols-3">
          <Card class="border-emerald-500/20">
            <CardContent class="pt-3 pb-3">
              <p class="text-xs text-muted-foreground">在线主机</p>
              <p class="text-xl font-bold mt-0.5 text-emerald-400">{{ nmapStats.online }}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent class="pt-3 pb-3">
              <p class="text-xs text-muted-foreground">离线主机</p>
              <p class="text-xl font-bold mt-0.5 text-muted-foreground">{{ nmapStats.offline }}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent class="pt-3 pb-3">
              <p class="text-xs text-muted-foreground">已发现主机</p>
              <p class="text-xl font-bold mt-0.5">{{ nmapStats.total }}</p>
            </CardContent>
          </Card>
        </div>

        <!-- 主机列表 -->
        <div class="rounded-lg border border-border overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-muted/30 border-b border-border">
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">IP 地址</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">MAC / 厂商</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">操作系统</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">OS 标签</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">状态</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">开放端口</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="nmapHostLoading">
                <td colspan="7" class="text-center py-10 text-muted-foreground text-sm">加载中...</td>
              </tr>
              <tr v-else-if="nmapHosts.length === 0">
                <td colspan="7" class="py-12">
                  <div class="flex flex-col items-center gap-2 text-muted-foreground">
                    <Monitor class="size-10 opacity-30" />
                    <span class="text-sm">暂无主机数据，请先执行 Nmap 扫描</span>
                  </div>
                </td>
              </tr>
              <tr v-for="host in nmapHosts" :key="host.id" class="border-b border-border/50 hover:bg-muted/20">
                <td class="px-4 py-2.5 font-mono text-sm font-medium">{{ host.ip }}</td>
                <td class="px-4 py-2.5">
                  <p class="font-mono text-xs">{{ host.mac_address || '—' }}</p>
                  <p class="text-xs text-muted-foreground">{{ host.vendor || '' }}</p>
                </td>
                <td class="px-4 py-2.5 text-xs max-w-[180px]">
                  <p class="truncate">{{ host.os_type || '未识别' }}</p>
                  <p v-if="host.os_accuracy" class="text-muted-foreground">精确度 {{ host.os_accuracy }}%</p>
                </td>
                <td class="px-4 py-2.5">
                  <span class="text-xs text-muted-foreground">—</span>
                </td>
                <td class="px-4 py-2.5">
                  <Badge :class="host.state === 'up' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-muted text-muted-foreground'">
                    {{ host.state }}
                  </Badge>
                </td>
                <td class="px-4 py-2.5 text-xs text-muted-foreground">
                  {{ Array.isArray(host.open_ports) ? host.open_ports.length : 0 }} 个端口
                </td>
                <td class="px-4 py-2.5">
                  <Button variant="ghost" size="sm" class="cursor-pointer h-6 text-xs gap-1" @click="openNmapHostDetail(host)">
                    <Eye class="size-3" />
                    详情
                  </Button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Nmap 主机分页 -->
        <div class="flex items-center justify-between text-sm text-muted-foreground">
          <span>共 {{ nmapHostTotal }} 台主机</span>
          <div class="flex gap-1">
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="nmapHostOffset === 0" @click="loadNmapHosts(nmapHostOffset - NMAP_LIMIT)">
              <ChevronLeft class="size-4" />
            </Button>
            <span class="px-3 py-1 text-xs">第 {{ Math.floor(nmapHostOffset / NMAP_LIMIT) + 1 }} 页</span>
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="nmapHostOffset + NMAP_LIMIT >= nmapHostTotal" @click="loadNmapHosts(nmapHostOffset + NMAP_LIMIT)">
              <ChevronRight class="size-4" />
            </Button>
          </div>
        </div>
      </TabsContent>

      <!-- ===== Tab: 发现资产 ===== -->
      <TabsContent value="discovered-assets" class="space-y-4">
        <!-- Toolbar -->
        <div class="flex items-center gap-3 flex-wrap">
          <Input
            v-model="discoveredIpFilter"
            placeholder="过滤 IP..."
            class="h-8 w-40 text-sm"
            @change="loadDiscoveredAssets(0)"
          />
          <Button variant="outline" size="sm" class="cursor-pointer gap-1 ml-auto" :disabled="discoveredLoading" @click="loadDiscoveredAssets(0)">
            <RefreshCw class="size-3.5" :class="discoveredLoading ? 'animate-spin' : ''" />
            刷新
          </Button>
        </div>

        <!-- 资产列表 -->
        <div class="rounded-lg border border-border overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-muted/30 border-b border-border">
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">IP 地址</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">MAC / 厂商</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">操作系统</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">开放端口</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">状态</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">最后发现时间</th>
                <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="discoveredLoading">
                <td colspan="7" class="text-center py-10 text-muted-foreground text-sm">加载中...</td>
              </tr>
              <tr v-else-if="discoveredAssets.length === 0">
                <td colspan="7" class="py-12">
                  <div class="flex flex-col items-center gap-2 text-muted-foreground">
                    <Scan class="size-10 opacity-30" />
                    <span class="text-sm">暂无发现资产，请先在 Nmap 主机 Tab 执行扫描</span>
                  </div>
                </td>
              </tr>
              <tr v-for="asset in discoveredAssets" :key="asset.id" class="border-b border-border/50 hover:bg-muted/20">
                <td class="px-4 py-2.5 font-mono text-sm font-medium text-primary cursor-pointer hover:underline" @click="openDiscoveredAssetDetail(asset)">
                  {{ asset.current_ip }}
                </td>
                <td class="px-4 py-2.5">
                  <p class="font-mono text-xs">{{ asset.mac_address || '—' }}</p>
                  <p class="text-xs text-muted-foreground">{{ asset.vendor || '' }}</p>
                </td>
                <td class="px-4 py-2.5 text-xs">{{ asset.os_type || '未识别' }}</td>
                <td class="px-4 py-2.5 text-xs text-muted-foreground">
                  {{ Array.isArray(asset.open_ports) ? asset.open_ports.length : 0 }} 个
                </td>
                <td class="px-4 py-2.5">
                  <Badge :class="asset.state === 'up' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-muted text-muted-foreground'">
                    {{ asset.state }}
                  </Badge>
                </td>
                <td class="px-4 py-2.5 text-xs text-muted-foreground">
                  {{ asset.last_seen?.slice(0, 19).replace('T', ' ') ?? '—' }}
                </td>
                <td class="px-4 py-2.5">
                  <Button variant="ghost" size="sm" class="cursor-pointer h-6 text-xs gap-1" @click="openDiscoveredAssetDetail(asset)">
                    <Eye class="size-3" />
                    历史
                  </Button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页 -->
        <div class="flex items-center justify-between text-sm text-muted-foreground">
          <span>共发现 {{ discoveredTotal }} 个资产</span>
          <div class="flex gap-1">
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="discoveredOffset === 0" @click="loadDiscoveredAssets(discoveredOffset - NMAP_LIMIT)">
              <ChevronLeft class="size-4" />
            </Button>
            <span class="px-3 py-1 text-xs">第 {{ Math.floor(discoveredOffset / NMAP_LIMIT) + 1 }} 页</span>
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="discoveredOffset + NMAP_LIMIT >= discoveredTotal" @click="loadDiscoveredAssets(discoveredOffset + NMAP_LIMIT)">
              <ChevronRight class="size-4" />
            </Button>
          </div>
        </div>
      </TabsContent>

      <!-- ===== Tab: 修复工单 ===== -->
      <TabsContent value="fix-tickets" class="space-y-4">
        <div class="flex items-center gap-3 flex-wrap">
          <div class="flex gap-1 flex-wrap">
            <Button
              v-for="s in ticketStatusOptions"
              :key="s.value"
              :variant="ticketStatusFilter === s.value ? 'default' : 'outline'"
              size="sm"
              class="cursor-pointer"
              @click="ticketStatusFilter = s.value; loadTickets(1)"
            >
              {{ s.label }}
            </Button>
          </div>
          <Button variant="outline" size="sm" class="cursor-pointer gap-1.5 ml-auto" :disabled="ticketLoading" @click="loadTickets(1)">
            <RefreshCw class="size-3.5" :class="ticketLoading ? 'animate-spin' : ''" />
            刷新
          </Button>
        </div>

        <div v-if="ticketLoading" class="text-center py-12 text-muted-foreground">加载中…</div>
        <div v-else-if="tickets.length === 0" class="text-center py-12 text-muted-foreground">
          <Wrench class="size-8 mx-auto mb-2 opacity-30" />
          <p class="text-sm">暂无修复工单</p>
        </div>
        <div v-else class="rounded-lg border border-border overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-muted/30 border-b border-border">
                <th class="px-4 py-2.5 text-left font-medium text-muted-foreground text-xs">ID</th>
                <th class="px-4 py-2.5 text-left font-medium text-muted-foreground text-xs">优先级</th>
                <th class="px-4 py-2.5 text-left font-medium text-muted-foreground text-xs">状态</th>
                <th class="px-4 py-2.5 text-left font-medium text-muted-foreground text-xs">负责人</th>
                <th class="px-4 py-2.5 text-left font-medium text-muted-foreground text-xs">截止日期</th>
                <th class="px-4 py-2.5 text-left font-medium text-muted-foreground text-xs">创建时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tickets" :key="t.id" class="border-b border-border/50 hover:bg-muted/20 transition-colors">
                <td class="px-4 py-2.5 font-mono text-xs">#{{ t.id }}</td>
                <td class="px-4 py-2.5">
                  <Badge :class="ticketPriorityColor(t.priority)" class="text-xs">{{ t.priority }}</Badge>
                </td>
                <td class="px-4 py-2.5">
                  <Badge variant="outline" class="text-xs">{{ t.status }}</Badge>
                </td>
                <td class="px-4 py-2.5 text-xs text-muted-foreground">{{ t.assignee || '—' }}</td>
                <td class="px-4 py-2.5 text-xs text-muted-foreground">{{ t.due_date?.slice(0, 10) || '—' }}</td>
                <td class="px-4 py-2.5 text-xs text-muted-foreground">{{ formatTime(t.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="ticketTotal > 20" class="flex items-center justify-between text-sm text-muted-foreground">
          <span>共 {{ ticketTotal }} 个工单</span>
          <div class="flex gap-1">
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="ticketPage <= 1" @click="loadTickets(ticketPage - 1)">
              <ChevronLeft class="size-4" />
            </Button>
            <span class="px-3 py-1 text-xs">第 {{ ticketPage }} 页</span>
            <Button variant="outline" size="sm" class="cursor-pointer" :disabled="ticketPage * 20 >= ticketTotal" @click="loadTickets(ticketPage + 1)">
              <ChevronRight class="size-4" />
            </Button>
          </div>
        </div>
      </TabsContent>

      <!-- ===== Tab: 攻击路径 ===== -->
      <TabsContent value="attack-path" class="space-y-4">
        <Card>
          <CardContent class="pt-6">
            <div class="flex items-center gap-3 mb-4">
              <Label>选择扫描任务</Label>
              <Select v-model="attackPathTaskId">
                <SelectTrigger class="w-60">
                  <SelectValue placeholder="选择已完成的扫描任务" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="t in completedTasks" :key="t.id" :value="String(t.id)">
                    #{{ t.id }} {{ t.target }} ({{ t.profile || 'default' }})
                  </SelectItem>
                </SelectContent>
              </Select>
              <Button size="sm" class="cursor-pointer gap-1.5" :disabled="!attackPathTaskId || attackPathLoading" @click="loadAttackPath">
                <Route class="size-3.5" />
                分析攻击路径
              </Button>
            </div>

            <div v-if="attackPathLoading" class="text-center py-16 text-muted-foreground">
              <RefreshCw class="size-6 mx-auto mb-2 animate-spin opacity-40" />
              <p class="text-sm">正在分析攻击路径…</p>
            </div>
            <div v-else-if="!attackPathData" class="text-center py-16 text-muted-foreground">
              <Route class="size-10 mx-auto mb-3 opacity-20" />
              <p class="text-sm">选择扫描任务后点击「分析攻击路径」查看横向移动分析结果</p>
            </div>
            <div v-else class="space-y-4">
              <div class="grid gap-3 md:grid-cols-3">
                <div class="rounded-lg border border-border p-3 space-y-1">
                  <p class="text-xs text-muted-foreground">高危节点</p>
                  <p class="text-2xl font-bold" :class="attackPathData.high_risk_nodes > 0 ? 'text-red-400' : 'text-emerald-400'">{{ attackPathData.high_risk_nodes }}</p>
                </div>
                <div class="rounded-lg border border-border p-3 space-y-1">
                  <p class="text-xs text-muted-foreground">横向移动路径</p>
                  <p class="text-2xl font-bold text-amber-400">{{ attackPathData.lateral_paths }}</p>
                </div>
                <div class="rounded-lg border border-border p-3 space-y-1">
                  <p class="text-xs text-muted-foreground">总节点数</p>
                  <p class="text-2xl font-bold text-foreground">{{ attackPathData.total_nodes }}</p>
                </div>
              </div>
              <div v-if="attackPathData.paths?.length" class="space-y-2">
                <p class="text-sm font-semibold">发现的攻击路径</p>
                <div v-for="(path, idx) in attackPathData.paths" :key="idx" class="rounded-lg border border-border p-3 space-y-1.5">
                  <div class="flex items-center gap-2">
                    <Badge :class="path.risk === 'HIGH' ? 'bg-red-500/15 text-red-400' : 'bg-amber-500/15 text-amber-400'" class="text-xs">{{ path.risk }}</Badge>
                    <span class="text-xs text-muted-foreground">{{ path.description }}</span>
                  </div>
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <template v-for="(node, ni) in path.nodes" :key="ni">
                      <code class="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">{{ node }}</code>
                      <span v-if="Number(ni) < path.nodes.length - 1" class="text-muted-foreground text-xs">→</span>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>

    <!-- 发现资产 IP 历史弹窗 -->
    <div
      v-if="assetHistoryOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      @click.self="assetHistoryOpen = false"
    >
      <div class="mx-4 w-full max-w-md rounded-xl border border-border bg-background shadow-2xl max-h-[70vh] flex flex-col">
        <div class="flex items-center justify-between border-b border-border px-5 py-4 shrink-0">
          <div class="flex items-center gap-2">
            <Scan class="size-4 text-primary" />
            <span class="font-semibold text-sm">扫描历史</span>
            <code class="text-xs text-muted-foreground ml-1">{{ selectedDiscoveredAsset?.current_ip }}</code>
          </div>
          <button class="text-muted-foreground hover:text-foreground" @click="assetHistoryOpen = false">
            <X class="size-4" />
          </button>
        </div>
        <div class="p-4 overflow-y-auto">
          <div v-if="assetHistoryLoading" class="py-6 text-center text-muted-foreground text-sm">加载中...</div>
          <div v-else-if="!assetHistory.length" class="py-6 text-center text-muted-foreground text-sm">暂无历史记录</div>
          <div v-else class="space-y-2">
            <div
              v-for="h in assetHistory"
              :key="h.id"
              class="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
            >
              <div class="flex items-center gap-3">
                <Badge :class="h.state === 'up' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-muted text-muted-foreground'" class="text-xs h-5">{{ h.state || '—' }}</Badge>
                <span class="font-mono text-xs">任务 #{{ h.scan_task_id }}</span>
              </div>
              <span class="text-xs text-muted-foreground">{{ h.seen_time?.slice(0, 19).replace('T', ' ') ?? '—' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Nmap 配置弹窗 -->
    <Dialog v-model:open="showNmapConfig">
      <DialogContent class="max-w-[520px]">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <SettingsIcon class="size-4 text-blue-400" />
            Nmap 扫描配置
          </DialogTitle>
          <DialogDescription>配置 Nmap 可执行路径与扫描目标，启用定时探测</DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-2">
          <div class="space-y-1.5">
            <Label>Nmap 可执行路径</Label>
            <Input v-model="nmapCfgForm.nmap_path" placeholder="C:\nmap\nmap.exe 或 /usr/bin/nmap" />
          </div>
          <div class="space-y-1.5">
            <Label>扫描 IP 范围（每行一个）</Label>
            <textarea
              v-model="nmapCfgIpText"
              rows="3"
              placeholder="192.168.1.0/24&#10;10.0.0.1-255"
              class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-none font-mono"
            />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <Label>扫描间隔（秒）</Label>
              <Input v-model.number="nmapCfgForm.scan_interval" type="number" :min="60" />
            </div>
            <div class="space-y-1.5">
              <Label>定时扫描</Label>
              <div class="flex items-center gap-2 h-9">
                <button
                  type="button"
                  role="switch"
                  :aria-checked="nmapCfgForm.enabled ? 'true' : 'false'"
                  :class="[
                    'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    nmapCfgForm.enabled ? 'bg-primary' : 'bg-input',
                  ]"
                  @click="nmapCfgForm.enabled = !nmapCfgForm.enabled"
                >
                  <span
                    :class="[
                      'pointer-events-none inline-block size-4 rounded-full bg-white shadow-lg ring-0 transition-transform',
                      nmapCfgForm.enabled ? 'translate-x-4' : 'translate-x-0',
                    ]"
                  />
                </button>
                <span class="text-sm text-muted-foreground">{{ nmapCfgForm.enabled ? '已开启' : '已关闭' }}</span>
              </div>
            </div>
          </div>
          <div v-if="nmapCfgMsg" :class="nmapCfgMsgOk ? 'text-emerald-400' : 'text-destructive'" class="text-xs">{{ nmapCfgMsg }}</div>
        </div>
        <DialogFooter>
          <Button variant="outline" size="sm" class="cursor-pointer" @click="showNmapConfig = false">取消</Button>
          <Button size="sm" class="cursor-pointer" :disabled="nmapCfgSaving" @click="saveNmapCfg">
            {{ nmapCfgSaving ? '保存中…' : '保存配置' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Nmap 主机详情弹窗 -->
    <NmapHostDetailDialog
      v-model:open="nmapHostDetailOpen"
      :ip="selectedNmapHost?.ip"
      :host="selectedNmapHost"
      title="主机详情"
    />

    <!-- Task Detail Dialog -->
    <Dialog v-model:open="showTaskDetail">
      <DialogContent class="max-w-[700px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <Shield class="size-5" />
            任务详情 #{{ selectedTask?.id }}
          </DialogTitle>
        </DialogHeader>
        <div v-if="selectedTask" class="space-y-4">
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div class="space-y-1">
              <p class="text-muted-foreground text-xs">目标</p>
              <p class="font-mono font-medium">{{ selectedTask.target }}</p>
            </div>
            <div class="space-y-1">
              <p class="text-muted-foreground text-xs">状态</p>
              <Badge :class="getStateColor(selectedTask.state)">{{ getStateLabel(selectedTask.state) }}</Badge>
            </div>
            <div class="space-y-1">
              <p class="text-muted-foreground text-xs">配置</p>
              <p>{{ selectedTask.profile || 'default' }}</p>
            </div>
            <div class="space-y-1">
              <p class="text-muted-foreground text-xs">工具</p>
              <p>{{ selectedTask.tool_name }}</p>
            </div>
            <div v-if="selectedTask.error_message" class="col-span-2 space-y-1">
              <p class="text-muted-foreground text-xs">错误信息</p>
              <p class="text-destructive text-xs font-mono bg-destructive/10 rounded p-2">{{ selectedTask.error_message }}</p>
            </div>
          </div>

          <div class="space-y-2">
            <p class="text-sm font-semibold">发现项（{{ selectedTaskFindings.length }}）</p>
            <div v-if="selectedTaskFindings.length === 0" class="text-sm text-muted-foreground text-center py-4 border border-dashed rounded-lg">
              暂无发现项
            </div>
            <div v-else class="rounded border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow class="bg-muted/30">
                    <TableHead class="text-xs">端口/服务</TableHead>
                    <TableHead class="text-xs">严重程度</TableHead>
                    <TableHead class="text-xs">状态</TableHead>
                    <TableHead class="text-xs">证据</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-for="f in selectedTaskFindings" :key="f.id">
                    <TableCell class="text-xs font-mono">{{ f.port }}/{{ f.service }}</TableCell>
                    <TableCell><Badge class="text-xs" :class="getSeverityColor(f.severity)">{{ f.severity }}</Badge></TableCell>
                    <TableCell><Badge variant="outline" class="text-xs">{{ f.status }}</Badge></TableCell>
                    <TableCell class="text-xs text-muted-foreground max-w-[200px] truncate">{{ f.evidence }}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>

    <!-- Finding Detail Dialog -->
    <Dialog v-model:open="showFindingDetail">
      <DialogContent class="max-w-[560px]">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <Bug class="size-5" />
            发现项详情
          </DialogTitle>
        </DialogHeader>
        <div v-if="selectedFinding" class="space-y-4 text-sm">
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1">
              <p class="text-muted-foreground text-xs">资产</p>
              <p class="font-mono">{{ selectedFinding.asset }}</p>
            </div>
            <div class="space-y-1">
              <p class="text-muted-foreground text-xs">端口/服务</p>
              <p>{{ selectedFinding.port }}/{{ selectedFinding.service || '未知' }}</p>
            </div>
            <div class="space-y-1">
              <p class="text-muted-foreground text-xs">严重程度</p>
              <Badge :class="getSeverityColor(selectedFinding.severity)">{{ selectedFinding.severity }}</Badge>
            </div>
            <div class="space-y-1">
              <p class="text-muted-foreground text-xs">CVE</p>
              <p class="font-mono">{{ selectedFinding.cve || '—' }}</p>
            </div>
          </div>
          <div class="space-y-1">
            <p class="text-muted-foreground text-xs">证据详情</p>
            <pre class="text-xs bg-muted/40 rounded-lg p-3 whitespace-pre-wrap font-mono overflow-auto max-h-48">{{ selectedFinding.evidence || '无证据' }}</pre>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { scanApi, type Asset, type ScanTask, type ScanFinding, type ScanProfile, type NmapHost, type NmapScan, type NmapStats, type VulnStats, type DiscoveredAsset, type AssetIpHistory } from '@/api/scan'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { AlertTriangle, ChevronLeft, ChevronRight, Eye, Monitor, Plus, RefreshCw, Route, Scan, Search, Settings as SettingsIcon, Shield, ShieldCheck, Target, Trash2, Bug, Wrench, X } from 'lucide-vue-next'
import NmapHostDetailDialog from '@/components/NmapHostDetailDialog.vue'
import { RealtimeChannel } from '@/api/realtime'
import { fixTicketApi, type FixTicket } from '@/api/fix-tickets'

// ===== Active Tab =====
const activeTab = ref('assets')

// ===== Assets =====
const assets = ref<Asset[]>([])
const assetTotal = ref(0)
const assetPage = ref(1)
const assetLoading = ref(false)
const assetKeyword = ref('')
const assetTypeFilter = ref('')
const showCreateAsset = ref(false)
const assetError = ref('')
const newAsset = ref({ target: '', target_type: 'IP', tags: '', description: '', enabled: true })

const loadAssets = async (page = 1) => {
  assetLoading.value = true
  assetError.value = ''
  try {
    const result = await scanApi.getAssets({
      keyword: assetKeyword.value || undefined,
      target_type: assetTypeFilter.value || undefined,
      page,
      page_size: 20,
    })
    assets.value = result.items
    assetTotal.value = result.total
    assetPage.value = page
  } catch (e) {
    console.error(e)
  } finally {
    assetLoading.value = false
  }
}

const createAsset = async () => {
  if (!newAsset.value.target.trim()) { assetError.value = '目标不能为空'; return }
  assetLoading.value = true
  assetError.value = ''
  try {
    await scanApi.createAsset({
      target: newAsset.value.target,
      target_type: newAsset.value.target_type,
      tags: newAsset.value.tags || undefined,
      description: newAsset.value.description || undefined,
      enabled: true,
    })
    showCreateAsset.value = false
    newAsset.value = { target: '', target_type: 'IP', tags: '', description: '', enabled: true }
    await loadAssets(1)
  } catch (e: any) {
    assetError.value = e?.response?.data?.message || e?.message || '创建失败'
  } finally {
    assetLoading.value = false
  }
}

const toggleAsset = async (asset: Asset) => {
  try {
    await scanApi.toggleAsset(asset.id)
    await loadAssets(assetPage.value)
  } catch (e) { console.error(e) }
}

const confirmDeleteAsset = (asset: Asset) => {
  if (window.confirm(`确认删除资产 ${asset.target}？此操作不可恢复。`)) {
    deleteAsset(asset.id)
  }
}

const deleteAsset = async (assetId: number) => {
  try {
    await scanApi.deleteAsset(assetId)
    await loadAssets(assetPage.value)
  } catch (e) { console.error(e) }
}

// ===== Profiles =====
const profiles = ref<ScanProfile[]>([])
const availableProfiles = computed(() => profiles.value.filter(p => p.available))
const selectedProfile = computed(() => profiles.value.find(p => p.key === newTask.value.profile))

const loadProfiles = async () => {
  try { profiles.value = await scanApi.getProfiles() } catch (e) { console.error(e) }
}

// ===== Tasks =====
const tasks = ref<ScanTask[]>([])
const taskTotal = ref(0)
const taskPage = ref(1)
const taskLoading = ref(false)
const taskStateFilter = ref('')
const showCreateTask = ref(false)
const taskError = ref('')
const newTask = ref({ target: '', profile: 'default', asset_id_str: '' })

const taskStateOptions = [
  { value: '', label: '全部' },
  { value: 'CREATED', label: '待调度' },
  { value: 'RUNNING', label: '运行中' },
  { value: 'REPORTED', label: '已完成' },
  { value: 'FAILED', label: '失败' },
]

const loadTasks = async (page = 1) => {
  taskLoading.value = true
  try {
    const result = await scanApi.getTasks({
      state: taskStateFilter.value || undefined,
      page,
      page_size: 20,
    })
    tasks.value = result.items
    taskTotal.value = result.total
    taskPage.value = page
  } catch (e) { console.error(e) } finally { taskLoading.value = false }
}

const createTask = async () => {
  if (!newTask.value.target.trim()) { taskError.value = '目标不能为空'; return }
  taskLoading.value = true
  taskError.value = ''
  try {
    await scanApi.createTask({
      target: newTask.value.target,
      profile: newTask.value.profile,
      asset_id: newTask.value.asset_id_str ? Number(newTask.value.asset_id_str) : undefined,
    })
    showCreateTask.value = false
    newTask.value = { target: '', profile: 'default', asset_id_str: '' }
    await loadTasks(1)
  } catch (e: any) {
    taskError.value = e?.response?.data?.message || e?.message || '创建失败'
  } finally { taskLoading.value = false }
}

const cancelTask = async (taskId: number) => {
  try {
    await scanApi.cancelTask(taskId)
    await loadTasks(taskPage.value)
  } catch (e) { console.error(e) }
}

// Task Detail
const showTaskDetail = ref(false)
const selectedTask = ref<ScanTask | null>(null)
const selectedTaskFindings = ref<ScanFinding[]>([])

const openTaskDetail = async (taskId: number) => {
  try {
    const data = await scanApi.getTask(taskId)
    selectedTask.value = data.task
    selectedTaskFindings.value = data.findings
    showTaskDetail.value = true
  } catch (e) { console.error(e) }
}

// ===== Findings =====
const findings = ref<ScanFinding[]>([])
const findingTotal = ref(0)
const findingPage = ref(1)
const findingLoading = ref(false)
const findingSeverityFilter = ref('')
const findingStatusFilter = ref('')

const findingSeverityOptions = [
  { value: '', label: '全部' },
  { value: 'HIGH', label: 'HIGH' },
  { value: 'MEDIUM', label: 'MEDIUM' },
  { value: 'LOW', label: 'LOW' },
  { value: 'INFO', label: 'INFO' },
]

const findingStatusOptions = [
  { value: '', label: '全部状态' },
  { value: 'NEW', label: 'NEW' },
  { value: 'CONFIRMED', label: 'CONFIRMED' },
  { value: 'FIXED', label: 'FIXED' },
]

const findingStatusUpdateOptions = ['NEW', 'CONFIRMED', 'FALSE_POSITIVE', 'FIXED', 'IGNORED']

const loadFindings = async (page = 1) => {
  findingLoading.value = true
  try {
    const result = await scanApi.getFindings({
      severity: findingSeverityFilter.value || undefined,
      status: findingStatusFilter.value || undefined,
      page,
      page_size: 20,
    })
    findings.value = result.items
    findingTotal.value = result.total
    findingPage.value = page
  } catch (e) { console.error(e) } finally { findingLoading.value = false }
}

const updateFindingStatus = async (findingId: number, status: string) => {
  try {
    await scanApi.updateFindingStatus(findingId, status)
    await loadFindings(findingPage.value)
  } catch (e) { console.error(e) }
}

// Finding Detail
const showFindingDetail = ref(false)
const selectedFinding = ref<ScanFinding | null>(null)
const openFindingDetail = (f: ScanFinding) => {
  selectedFinding.value = f
  showFindingDetail.value = true
}

// ===== Helpers =====
const formatTime = (t?: string | null) => {
  if (!t) return '—'
  return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const calcDuration = (start?: string, end?: string) => {
  if (!start) return '—'
  const endTime = end ? new Date(end) : new Date()
  const diff = Math.round((endTime.getTime() - new Date(start).getTime()) / 1000)
  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m${diff % 60}s`
  return `${Math.floor(diff / 3600)}h${Math.floor((diff % 3600) / 60)}m`
}

const getStateColor = (state: string) => {
  const map: Record<string, string> = {
    CREATED: 'bg-muted text-muted-foreground border-border',
    DISPATCHED: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    RUNNING: 'bg-blue-500/20 text-blue-300 border-blue-500/40 animate-pulse',
    PARSED: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
    REPORTED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    FAILED: 'bg-destructive/15 text-destructive border-destructive/30',
  }
  return map[state] || 'bg-muted text-muted-foreground'
}

const getStateLabel = (state: string) => {
  const map: Record<string, string> = {
    CREATED: '待调度', DISPATCHED: '已分发', RUNNING: '运行中',
    PARSED: '解析中', REPORTED: '已完成', FAILED: '失败',
  }
  return map[state] || state
}

const getSeverityColor = (severity: string) => {
  const map: Record<string, string> = {
    HIGH: 'bg-red-500/15 text-red-400 border-red-500/30',
    MEDIUM: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    LOW: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    INFO: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  }
  return map[severity] || 'bg-muted text-muted-foreground'
}

// ===== Vuln Stats & Scan =====
const vulnStats = ref<VulnStats | null>(null)
const vulnScanning = ref(false)

const loadVulnStats = async () => {
  try {
    vulnStats.value = await scanApi.getVulnStats()
  } catch (e) { console.error(e) }
}

const triggerVulnScan = async () => {
  vulnScanning.value = true
  try {
    await scanApi.triggerVulnScan()
    setTimeout(() => { loadVulnStats(); vulnScanning.value = false }, 3000)
  } catch (e) { console.error(e); vulnScanning.value = false }
}

// ===== Nmap 主机 =====
const NMAP_LIMIT = 50
const nmapHosts = ref<NmapHost[]>([])
const nmapScans = ref<NmapScan[]>([])
const nmapStats = ref<NmapStats | null>(null)
const nmapHostTotal = ref(0)
const nmapHostOffset = ref(0)
const nmapHostLoading = ref(false)
const nmapScanning = ref(false)
const selectedScanId = ref<number | ''>('')
const nmapStateFilter = ref('')

// Nmap 主机详情弹窗
const nmapHostDetailOpen = ref(false)
const selectedNmapHost = ref<NmapHost | null>(null)

const openNmapHostDetail = (host: NmapHost) => {
  selectedNmapHost.value = host
  nmapHostDetailOpen.value = true
}

const loadNmapScans = async () => {
  try {
    nmapScans.value = await scanApi.getNmapScans()
  } catch (e) { console.error(e) }
}

const loadNmapStats = async () => {
  try {
    nmapStats.value = await scanApi.getNmapStats()
  } catch (e) { console.error(e) }
}

const loadNmapHosts = async (offset = 0) => {
  nmapHostLoading.value = true
  nmapHostOffset.value = offset
  try {
    const result = await scanApi.getNmapHosts({
      scan_id: selectedScanId.value || undefined,
      state: nmapStateFilter.value || undefined,
      limit: NMAP_LIMIT,
      offset,
    })
    nmapHosts.value = result.items
    nmapHostTotal.value = result.total
  } catch (e) { console.error(e) } finally { nmapHostLoading.value = false }
}

const triggerNmapScan = async () => {
  nmapScanning.value = true
  try {
    await scanApi.triggerNmapScan()
    setTimeout(() => {
      loadNmapScans(); loadNmapHosts(); loadNmapStats()
      nmapScanning.value = false
    }, 5000)
  } catch (e) { console.error(e); nmapScanning.value = false }
}

// ===== Nmap 配置弹窗 =====
const showNmapConfig = ref(false)
const nmapCfgForm = reactive({ nmap_path: '', scan_interval: 604800, enabled: false })
const nmapCfgIpText = ref('')
const nmapCfgSaving = ref(false)
const nmapCfgMsg = ref('')
const nmapCfgMsgOk = ref(true)

const openNmapConfigDialog = async () => {
  nmapCfgMsg.value = ''
  try {
    const cfg = await scanApi.getNmapConfig()
    nmapCfgForm.nmap_path = cfg.nmap_path ?? ''
    nmapCfgForm.scan_interval = cfg.scan_interval ?? 604800
    nmapCfgForm.enabled = Boolean(cfg.enabled)
    nmapCfgIpText.value = Array.isArray(cfg.ip_ranges) ? cfg.ip_ranges.join('\n') : ''
  } catch { /* use defaults */ }
  showNmapConfig.value = true
}

const saveNmapCfg = async () => {
  if (!nmapCfgForm.nmap_path.trim()) {
    nmapCfgMsg.value = '请填写 Nmap 路径'
    nmapCfgMsgOk.value = false
    return
  }
  nmapCfgSaving.value = true
  nmapCfgMsg.value = ''
  try {
    const ipRanges = nmapCfgIpText.value.split('\n').map(s => s.trim()).filter(Boolean)
    await scanApi.saveNmapConfig({
      nmap_path: nmapCfgForm.nmap_path,
      ip_ranges: ipRanges,
      scan_interval: nmapCfgForm.scan_interval,
      enabled: nmapCfgForm.enabled,
    })
    nmapCfgMsg.value = '保存成功'
    nmapCfgMsgOk.value = true
    setTimeout(() => { showNmapConfig.value = false }, 800)
  } catch {
    nmapCfgMsg.value = '保存失败'
    nmapCfgMsgOk.value = false
  } finally {
    nmapCfgSaving.value = false
  }
}

// ===== 发现资产 =====
const discoveredAssets = ref<DiscoveredAsset[]>([])
const discoveredTotal = ref(0)
const discoveredOffset = ref(0)
const discoveredLoading = ref(false)
const discoveredIpFilter = ref('')
const assetHistoryOpen = ref(false)
const assetHistoryLoading = ref(false)
const assetHistory = ref<AssetIpHistory[]>([])
const selectedDiscoveredAsset = ref<DiscoveredAsset | null>(null)

const loadDiscoveredAssets = async (offset = 0) => {
  discoveredLoading.value = true
  discoveredOffset.value = offset
  try {
    const result = await scanApi.getDiscoveredAssets({
      ip: discoveredIpFilter.value || undefined,
      limit: NMAP_LIMIT,
      offset,
    })
    discoveredAssets.value = result.items
    discoveredTotal.value = result.total
  } catch (e) { console.error(e) } finally { discoveredLoading.value = false }
}

const openDiscoveredAssetDetail = async (asset: DiscoveredAsset) => {
  selectedDiscoveredAsset.value = asset
  assetHistory.value = []
  assetHistoryOpen.value = true
  assetHistoryLoading.value = true
  try {
    assetHistory.value = await scanApi.getAssetIpHistory(asset.current_ip)
  } catch (e) { console.error(e) } finally { assetHistoryLoading.value = false }
}

// ===== Fix Tickets =====
const tickets = ref<FixTicket[]>([])
const ticketTotal = ref(0)
const ticketPage = ref(1)
const ticketLoading = ref(false)
const ticketStatusFilter = ref('')

const ticketStatusOptions = [
  { value: '', label: '全部' },
  { value: 'OPEN', label: '待处理' },
  { value: 'IN_PROGRESS', label: '处理中' },
  { value: 'RESOLVED', label: '已解决' },
  { value: 'VERIFIED', label: '已验证' },
  { value: 'CLOSED', label: '已关闭' },
]

const ticketPriorityColor = (priority: string) => {
  const map: Record<string, string> = {
    P0: 'bg-red-500/15 text-red-400 border-red-500/30',
    P1: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    P2: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    P3: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  }
  return map[priority] || 'bg-muted text-muted-foreground'
}

const loadTickets = async (page = 1) => {
  ticketLoading.value = true
  try {
    const result = await fixTicketApi.list({
      status: ticketStatusFilter.value || undefined,
      page,
      page_size: 20,
    })
    tickets.value = result.items
    ticketTotal.value = result.total
    ticketPage.value = page
  } catch (e) { console.error(e) } finally { ticketLoading.value = false }
}

// ===== Attack Path =====
const attackPathTaskId = ref('')
const attackPathLoading = ref(false)
const attackPathData = ref<any>(null)

const completedTasks = computed(() => tasks.value.filter(t => t.state === 'REPORTED'))

const loadAttackPath = async () => {
  if (!attackPathTaskId.value) return
  attackPathLoading.value = true
  attackPathData.value = null
  try {
    const res = await scanApi.getAttackPath(Number(attackPathTaskId.value))
    attackPathData.value = res
  } catch (e) { console.error(e) } finally { attackPathLoading.value = false }
}

// ===== Init =====
watch(activeTab, (tab) => {
  if (tab === 'assets') loadAssets(1)
  else if (tab === 'tasks') loadTasks(1)
  else if (tab === 'findings') { loadFindings(1); loadVulnStats() }
  else if (tab === 'nmap-hosts') { loadNmapHosts(); loadNmapScans(); loadNmapStats() }
  else if (tab === 'discovered-assets') loadDiscoveredAssets(0)
  else if (tab === 'fix-tickets') loadTickets(1)
  else if (tab === 'attack-path') { if (!tasks.value.length) loadTasks(1) }
})

let _scanWsChannel: RealtimeChannel | null = null
let _scanRefreshTimer: ReturnType<typeof setTimeout> | null = null

const scheduleScanRefresh = () => {
  if (_scanRefreshTimer) return
  _scanRefreshTimer = setTimeout(() => {
    _scanRefreshTimer = null
    if (activeTab.value === 'tasks') void loadTasks(taskPage.value)
    else if (activeTab.value === 'nmap-hosts') void loadNmapHosts(nmapHostOffset.value)
    else if (activeTab.value === 'findings') void loadFindings(findingPage.value)
  }, 150)
}

onMounted(async () => {
  await Promise.all([loadAssets(1), loadProfiles()])
  _scanWsChannel = new RealtimeChannel('/ws/scan/tasks', {
    onEvent: (event) => {
      if (event.type === 'ready') return
      scheduleScanRefresh()
    },
  })
  _scanWsChannel.connect()
})

onUnmounted(() => {
  if (_scanRefreshTimer) { clearTimeout(_scanRefreshTimer); _scanRefreshTimer = null }
  _scanWsChannel?.close()
  _scanWsChannel = null
})
</script>
