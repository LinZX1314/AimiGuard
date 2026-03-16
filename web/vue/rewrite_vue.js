const fs = require('fs')

let code = fs.readFileSync('src/views/AiChatView.vue.tmp', 'utf8')

const imports = `
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { MessageSquare, Plus, Trash2, Bot, User, Mic, MicOff, Volume2, VolumeX, Send, ChevronDown, CheckCircle2, Wrench, ChevronUp } from 'lucide-vue-next'
`

code = code.replace(/<script setup lang="ts">\n/, `<script setup lang="ts">\n${imports}\n`)

fs.writeFileSync('src/views/AiChatView.vue.tmp', code)
