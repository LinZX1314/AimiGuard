<template>
  <Transition name="route-progress">
    <div v-if="isRouteChanging" class="route-progress" :style="{ transform: `scaleX(${routeProgress})` }" />
  </Transition>
  <div ref="shellRef" class="flex h-screen flex-col bg-background/50 text-foreground">
    <header class="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div class="flex h-14 items-center px-4 sm:px-6">
        <div class="flex items-center gap-3">
          <Sheet>
            <SheetTrigger as-child>
              <Button variant="ghost" size="icon" class="cursor-pointer md:hidden">
                <PanelLeft class="size-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" class="w-[18rem] border-r border-border bg-sidebar p-0">
              <SheetHeader class="sr-only">
                <SheetTitle>Mobile Navigation</SheetTitle>
                <SheetDescription>Mobile navigation menu for current mode.</SheetDescription>
              </SheetHeader>
              <div class="border-b border-sidebar-border px-4 py-3">
                <p class="text-sm font-medium text-sidebar-foreground">{{ activeModeLabel }}</p>
              </div>
              <nav class="space-y-1 p-3">
                <router-link
                  v-for="item in currentSidebarItems"
                  :key="item.to"
                  :to="item.to"
                  class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-sidebar-foreground transition-[transform,opacity] duration-220 hover:-translate-y-px hover:bg-sidebar-accent hover:opacity-95 cursor-pointer"
                  active-class="bg-sidebar-accent text-sidebar-accent-foreground"
                >
                  <component :is="item.icon" class="size-4" />
                  <span>{{ item.label }}</span>
                </router-link>
              </nav>
            </SheetContent>
          </Sheet>

          <div class="flex items-center gap-2">
            <ShieldCheck class="size-5 text-primary" />
            <span class="hidden text-sm font-semibold tracking-tight text-foreground sm:inline">AI Guardian</span>
          </div>
        </div>

        <div class="flex flex-1 justify-center">
          <Tabs
            :model-value="activeMode"
            class="hidden md:flex"
            @update:model-value="onModeChange"
          >
            <TabsList class="h-9 w-auto bg-muted/50 p-1 rounded-lg gap-1">
              <TabsTrigger 
                value="defense" 
                class="cursor-pointer px-3 text-xs sm:text-sm rounded-md transition-[transform,opacity] duration-220 hover:-translate-y-px 
                data-[state=active]:!bg-[#3B82F6] data-[state=active]:!text-white data-[state=active]:shadow-sm
                hover:text-[#3B82F6] data-[state=active]:hover:text-white"
              >
                闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁绘劦鍓欓崝銈囩磽瀹ュ拑韬€殿喖顭烽幃銏ゅ礂鐏忔牗瀚介梺璇查叄濞佳勭珶婵犲伣锝夘敊閸撗咃紲闂佺粯鍔﹂崜娆撳礉閵堝洨纾界€广儱鎷戦煬顒傗偓娈垮枛椤兘骞冮姀銈呯閻忓繑鐗楃€氫粙姊虹拠鏌ュ弰婵炰匠鍕彾濠电姴浼ｉ敐澶樻晪闁逞屽墮椤繘宕崟鎳峰洤鐐婄憸澶愬磻閹捐围濠㈣泛锕﹂悰銉モ攽鎺抽崐鏇㈠箠鎼淬埄鏀伴梻鍌欑閹测€趁洪敃鍌氬瀭濞村吋娼欑粈鍐煃瑜滈崜鐔奉潖濞差亝顥堟繛娣€栭惄顖氱暦閵娾晩鏁嶆繝濠傛噹閻愬﹥绻濋悽闈浶ラ柡浣规倐瀹曟垵鈽夐姀鈥充槐闂侀潧臎閸愩劎浜伴柣搴″帨閸嬫捇鏌嶈閸撴稑危閹扮増鍊烽悗闈涙憸閻﹀牓姊洪幖鐐插妧闁糕剝蓱閸熷搫鈹戦悩鍨毄闁稿鍋ゅ畷褰掝敍閻愭彃鐎梺闈╁瘜閸樼偓绋夊鍡欑闁瑰瓨鐟ラ悘顏堟煟閹惧瓨绀嬮柣鎿冨亰瀹曞爼濡搁敃鈧棄宥夋⒑閻熸澘绾ч柟顔煎€垮濠氬Χ婢跺鍎銈嗗姧缁茬粯绂掗姀鐘斀妞ゆ梻銆嬫Λ姘箾閸滃啰鎮兼俊鍙夊姍楠炴帡骞婂畷鍥ф灈闁圭厧缍婂畷鐑筋敇閻旈攱鐝梻鍌氬€搁崐鐑芥倿閿旈敮鍋撶粭娑樺幘妤﹁法鐤€婵炴垶顭囬敍娆忊攽閻樼粯娑ф俊顐ｆ尦閹虫捇宕归琛″亾閹烘埈娼╅柨婵嗘噸婢规洘绻濆▓鍨灈闁挎洏鍔岄埢宥夋晲閸ヮ煈娼熼梺鍦劋閸わ箓鎮㈤懡銈囨澑闂佹寧绻傜€氼噣鎯勬惔銊︾叄濞村吋鐟ч崚浼存煃鐟欏嫬鐏撮柟顔规櫊瀹曪絾寰勭€ｎ偄鈧绱撴担鍝勪壕闁稿骸鍟块…鍥晸閻樺啿浜楀銈嗗姧缁犳垿鎮欐繝鍥ㄧ厪濠电倯鈧崑鎾斥攽椤斿吋鍠樻慨濠冩そ楠炲酣鎳為妷锔芥闂備焦鎮堕崝灞筋焽閿熺姷宓侀柛鎰靛枟閻撱儵鎮楅敐搴′簻妞ゅ孩鎹囧濠氬磼濮樺崬顤€缂備礁顑呴悧鎾崇暦閹达箑绠婚悹鍥ㄥ絻瀹撳棝姊洪棃娑氱濠殿喚鍏樺畷婵嬫晝閳ь剟鈥旈崘顔嘉ч柛鈩冾殘閻熸劙姊洪悡搴ｆ瀮闁糕晜鐗犲鏌ュ醇閺囩偛鐎銈嗗姦閸嬪懘顢欓弮鍫熲拺缂備焦锚婵矂鎮樿箛鏃傛噭闁哄懎鐖奸弫鍐焵椤掑嫬鐓橀柟杈剧畱閻掓椽鏌涢幇銊︽珔闁逞屽墯閸旀洟鍩為幋锔芥櫖闁告洦鍋勯獮瀣渻閵堝啫鐏柣鐔叉櫊楠炴劖绻濋崘銊х獮閻庡厜鍋撻柍褜鍓氬鍕礋椤栨稈鎷婚梺绋挎湰閼归箖鍩€椤掑倸鍘撮柟铏殜瀹曟粍鎷呴悷鏉垮箲闂備礁澹婇崑鍛洪弽顐ょ焼闁割偆鍠撶弧鈧梻鍌氱墛娓氭宕曞澶嬬厓鐟滄粓宕滃▎鎾崇柈闁哄鍨归弳锕傛煏婵犲繘妾紓宥呮喘閺屾盯骞樺Δ鈧幊澶娢涢妸銉㈡斀闁挎稑瀚禍濂告煕婵犲啰澧电€规洘绻嗛ˇ瑙勬叏婵犱胶鐭欑€规洜鍠栭、娑橆潩閸楃偛绠?
              </TabsTrigger>
              <TabsTrigger 
                value="probe" 
                class="cursor-pointer px-3 text-xs sm:text-sm rounded-md transition-[transform,opacity] duration-220 hover:-translate-y-px 
                data-[state=active]:!bg-[#F97316] data-[state=active]:!text-white data-[state=active]:shadow-sm
                hover:text-[#F97316] data-[state=active]:hover:text-white"
              >
                婵犵數濮烽弫鍛婃叏閻戣棄鏋侀柛娑橈攻閸欏繘鏌ｉ幋锝嗩棄闁哄绶氶弻娑樷槈濮楀牊鏁鹃梺鍛婄懃缁绘﹢寮婚敐澶婄闁挎繂妫Λ鍕⒑閸濆嫷鍎庣紒鑸靛哺瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁绘劦鍓欓崝銈嗐亜椤撶姴鍘寸€殿喖顭烽弫鎰緞婵犲嫮鏉告俊鐐€栫敮濠囨倿閿曞倸纾块柟鍓х帛閳锋垿鏌熼懖鈺佷粶濠碘€炽偢閺屾稒绻濋崒娑樹淮閻庢鍠涢褔鍩ユ径鎰潊闁冲搫鍊瑰▍鍥⒒娴ｇ懓顕滅紒璇插€歌灋婵炴垟鎳為崶顒€唯鐟滃繒澹曢挊澹濆綊鏁愰崨顔藉創闁哄稄绻濋幃宄邦煥閸曨剛鍑￠梺鍝ュ枎閻°劍绌辨繝鍥х妞ゆ棁鍋愰濠囨⒑鐟欏嫭鍎楅柛妯圭矙瀹曟捇鎮介崨濞炬嫼闂佸湱顭堝ù椋庣不閹剧粯鐓欓柛鎰皺鏍＄紓浣规⒒閸犳牕顕ｉ幘顔藉亜闁告挷鑳堕悾楣冩⒒娴ｈ櫣甯涢柛鏃撻檮缁傚秴顭ㄩ崼婵堝姦濡炪倖甯婄粈渚€鎮樼€电硶鍋撶憴鍕缂傚秴锕獮鍐煥閸忓墽鍠撴禍鎼佸冀閵婏附娈兼繝鐢靛Х閺佹悂宕戝☉妯滅喐绻濋崶褏鍔﹀銈嗗笒椤︻喚鑺辩紒妯肩鐎瑰壊鍠栧顕€鏌ｅ☉鍗炴灍闁诡垱妫冩俊鎼佹晝閳ь剙鈻撻悢鍏尖拺闂傚牊鍐荤槐锟犳煕閹扳晛濡挎い鎾跺帶閳规垿鎮╅崹顐ｆ瘎闂佺顑囬崑銈夌嵁閹邦厾绡€婵﹩鍘煎▓鐐翠繆閵堝繒鍒伴柛鐕佸灦瀹曟劙鎳滈悽鐢电槇闂傚倸鐗婄粙鎺撳緞閸曨垱鐓曟繛鍡楃箳缁犲鏌＄仦鍓р槈闁伙絾绻堥崺鈧い鎺戝绾惧鏌ｉ幇顔煎妺闁稿鍊块弻锟犲炊閵夈儳浠鹃梺缁樻尭閸熸挳寮诲☉妯锋斀闁糕剝顨忔导宀勬⒑缁嬪灝顒㈤柛銊ユ贡濡叉劙骞掑Δ鈧悡銏ゆ煃瑜滈崜鐔风暦閹达箑绠荤紓浣诡焽閸樹粙鏌熼崗鑲╂殬闁稿鍊曢…鍥箛椤撶姷顔曢梺鍦帛鐢偟绮婚懡銈傚亾鐟欏嫭绀冪紒璇茬墦閻涱喚鈧綆鍠楅弲婊堟偠濞戞巻鍋撻崗鍛棜濠电偠鎻徊鑺ョ珶婵犲偆鐒介柕濞炬櫆閻撳啰鎲稿鍫濈闁绘棁鍋愬畵渚€鏌涢幇闈涙珮闁轰礁鍊块弻娑㈩敃閿濆洨鐣奸梺鍛婃缁犳垿鈥旈崘顔嘉ч柛鈩冾殘閻熴劑鏌ｆ惔銏犲毈闁告挾鍠栭獮濠傤煥閸涱喖鏋傞梺鍛婃处閸橀箖顢欓弴銏″€甸柣鐔告緲椤ュ繘鏌涢悩铏闁奸缚椴哥缓浠嬪川婵犲嫬甯楅梻鍌欑閻忔繈顢栭崨顖滅當闁圭儤顨嗛悡蹇涙煕閳╁厾顏嗙箔閹烘挶浜滄い鎰剁悼缁犵偤鏌℃担鐟板鐎规洏鍔戦、妤呭焵椤掑媻澶婎潩椤戣姤鏂€闂佺粯锚閻忔岸寮抽埡鍛厱閻庯綆鍋撻懓璺ㄢ偓瑙勬礈婵炩偓闁诡喒鏅濋幏鐘绘嚑椤掑效闂傚倷绀佹竟濠囨偂閸儱纾婚柟鐑橆殔閻ゎ喚鈧箍鍎遍ˇ浼村煕閹烘垟鏀介柣妯荤叀椤庢霉濠婂嫮鐭嬬紒缁樼〒閹风姾顦撮柣锝変憾閹繝濡堕崱妯哄伎濠碉紕鍋犻褎绂嶆ィ鍐┾拺闁圭娴风粻姗€鏌涚€ｃ劌鈧洟顢氶敐澶婄妞ゆ梻鈷堝濠囨⒑閹稿海鈽夐悗姘煎墴閻涱噣骞囬悧鍫氭嫽婵炶揪缍€椤宕戦悩缁樼厱閹兼惌鍠栭悘锔锯偓瑙勬礃濞茬喖寮婚崱妤婂悑闁糕剝銇涢崑鎾诲醇閺囩喓鍘撻梺鍛婄箓鐎氼參宕宠ぐ鎺撶厽?
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div class="flex items-center gap-2">
          <Sheet>
            <SheetTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                class="relative cursor-pointer text-muted-foreground"
              >
                <Bell class="size-4" />
                <span
                  v-if="unreadNotifications > 0"
                  class="absolute -top-0.5 -right-0.5 inline-flex h-2 w-2 rounded-full bg-red-500"
                />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" class="w-[22rem] border-l border-border p-0 gap-0">
              <!-- 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閹冣挃闁硅櫕鎹囬垾鏃堝礃椤忎礁浜鹃柨婵嗙凹缁ㄥジ鏌熼惂鍝ョМ闁哄矉缍侀、姗€鎮欓幖顓燁棧闂備線娼уΛ娆戞暜閹烘缍栨繝闈涱儐閺呮煡鏌涘☉鍗炲妞ゃ儲鑹鹃埞鎴炲箠闁稿﹥顨嗛幈銊╂倻閽樺锛涢梺缁樺姉閸庛倝宕戠€ｎ喗鐓熸俊顖濆吹濠€浠嬫煃瑜滈崗娑氭濮橆剦鍤曢柟缁㈠枛椤懘鏌ｅΟ鑽ゅ灩闁搞儯鍔庨崢閬嶆⒑闂堟侗妲堕柛銊ユ惈閳诲秹宕堕浣哄幈濠碘槅鍨抽崢褔鍩㈤崼鐔稿弿濠电姴瀚敮娑㈡煙瀹勭増鍤囩€规洏鍔嶇换婵嬪礃閵娿儱顥掓繝纰夌磿閸嬫垿宕愯缁辨挸顫濈捄铏诡攨闂佸憡鍔樼亸娆撳汲閿曞倹鈷掗柛顐ゅ枍缁惰鲸绻涚亸鏍ㄦ珕闁靛洤瀚伴獮瀣偐闊厽鍕冩繝纰夌磿閸嬫鍒掑▎鎾澄ュ〒姘ｅ亾鐎殿噮鍓欓埢搴ㄥ箚瑜庨崐顖炴⒒娴ｈ櫣銆婇柛鎾寸箚閹筋偊姊虹紒妯肩畺缂佽鍊块崺鐐哄箣閿旇姤娅栭梺鍛婃处閸嬪倿寮堕銏♀拺缂佸顑欓悞楣冩煕婵犲啰绠撻柣锝囧厴楠炲鏁冮埀顒傜不閾忣偂绻嗛柕鍫濆€告禍鍓х磽娴ｆ彃浜鹃梺绋挎湰缁嬫帡宕ｈ箛鏂剧箚闁绘劙顤傞崵娆徝瑰鍫㈢暫闁诡喗顨堥幉鎾礋椤掑偆妲伴梻浣规偠閸斿苯顭囬敓鐘冲仒妞ゆ柨妲堥悢鐓庣闁绘挸娴疯ぐ鎾⒒娴ｈ棄浜归柍宄扮墦瀹曟粓濡歌椤洟鏌涘▎蹇ｆШ缂佲檧鍋撻梻浣圭湽閸ㄨ棄顭囪缁傛帡鏁冮崒娑氬幈闂侀潧顭堥崕鎶藉春閿濆洠鍋撶憴鍕闁荤啿鏅犻獮鍐倻閽樺鐤囨繝鐢靛Т閸婅崵绮旈搹鍏夊亾鐟欏嫭绀堥柛鐘崇墵閵嗕礁鈽夊Ο閿嬵潔濠殿喗锕╅崜娆戠不濞差亝鈷掑ù锝囧劋閸も偓闂佸憡鑹鹃澶愮嵁閸℃鏆嗛柛鏇ㄥ亜閻庮參鎮楃憴鍕婵炲眰鍔戦幆宀勫箻缂佹ǚ鎷婚梺鍓插亞閸犳洟鍩€椤戣法鐭欓柟顔惧厴閺屽洭鏁傞幆褍姹查梻鍌欑閹测€趁洪敃鍌氬偍濡わ絽鍟崑鍌氼熆閼搁潧濮堥柛?-->
              <div class="border-b border-border px-4 py-3 shrink-0">
                <SheetTitle class="text-sm font-semibold">Notifications</SheetTitle>
                <SheetDescription class="sr-only">View realtime notifications and mark all as read.</SheetDescription>
              </div>
              <!-- 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁诡垎鍐ｆ寖闂佺娅曢幑鍥灳閺冨牆绀冩い蹇庣娴滈箖鏌ㄥ┑鍡欏嚬缂併劎绮妵鍕箳鐎ｎ亞浠鹃梺闈涙搐鐎氫即鐛崶顒夋晜闁糕剝鐟ч崢顖炴⒒娴ｅ憡鎯堥悶姘煎亰瀹曟繈骞嬮敃鈧粻鏍煏韫囧鈧洘瀵奸悩缁樼厱闁哄洨鍠庨悘鐔兼煕閵娿儺鐓奸柟顖楀亾濡炪倕绻愰悧鍡欑不濮樿鲸鍠愭繝濠傜墛閸嬪倸鈹戦崒姘暈闁绘挻鐩幃姗€鎮欓幓鎺嗘寖闂佸疇妫勯ˇ鐢稿蓟瀹ュ瀵犲鑸瞪戦埢鍫ユ倵鐟欏嫭绌跨紒缁樼箞楠炲啫鈻庨幘宕囶唽闂佸湱鍎ょ换鍌涗繆瑜庣换婵嬫偨闂堟刀銉╂煛娴ｈ鍊愮€规洘鍨甸埥澶愬閳ュ啿澹勯梻浣虹帛閸ㄧ厧螞閸曨垱鍋Δ锝呭暞閻撶喐淇婇娑卞劌闁搞倖鐟╅弻锕傚礃椤忓嫭鐏堥梺鍝勭焿缁绘繂鐣烽崼鏇炵厸濞达絽婀辨禍鏍磽閸屾瑨鍏屽┑鐐╁亾缂備胶濮甸悧鐘差嚕婵犳碍鏅插璺猴功閻も偓闂傚倸鍊搁悧濠勭矙閹达讣缍栨い蹇撶墛閳锋垹绱撴担璇＄劷缂佺姵鐗楃换娑㈡嚑椤掆偓閺嬪孩銇勯銏㈢闁圭厧缍婂畷鐑筋敇閻橀潧骞嗗┑鐘垫暩閸嬫稑螞濞嗘挸纾块柟鎯版缁€鍫澝归悡搴ｆ憼闁抽攱鍨圭槐鎺斺偓锝庝簻閻紕鈧鎮堕崕鑼崲濞戞矮鐒婇柡宥冨€曟禍楣冩煙妫颁胶顦︽繛鍫涘妽缁绘繈鎮介棃娴讹綁鏌ら崷顓炰壕闁稿寒鍋婂缁樻媴缁嬫寧姣愰梺鍦拡閸嬪﹤鐣烽幇鏉垮窛濠电姴瀚峰ú绋库攽閻樿宸ラ柣妤€锕崺娑㈠箣閿旂晫鍘卞┑鐐村灦閿曨偊宕濋悢铏圭＜闁绘娅曞畷宀勬煙椤旂瓔娈旀い顐ｇ箞椤㈡鎷呴崨濠勬毈婵犵數濮甸鏍窗閹烘纾婚柟鍓х帛閳锋垿姊婚崼鐔恒€掔紒鐘靛仱閺屾盯濡搁妷顔惧悑闂佽桨绀佺粔鎾€﹂妸鈺侀唶闁绘柨寮剁€氬ジ姊婚崒娆戣窗闁稿妫濆畷鎴濃槈閵忊€虫濡炪倖鐗楃粙鎺戔枍閻樼粯鍊甸柣銏㈡暩閵嗗﹪鏌涚€ｎ偅灏甸柟鍙夋尦瀹曠喖顢楅崒銈喰氶梺璇叉唉椤煤閿曞倸绀堟繝闈涱儐閸婂爼鏌熼悜姗嗘畷闁抽攱鍨垮濠氬醇濮橆厽鐝旈梺浼欓檮缁捇寮诲☉姗嗘建闁逞屽墰缁寮介鐐电暫闂佺粯鍔﹂崗娆撳磻閸涘瓨鐓曢柟鑸妽閺夊綊鏌熸搴ｅ笡缂佺粯鐩獮姗€寮堕幋鐘插Р闂備胶顭堥鍡涘箰閼姐倖宕叉繛鎴炵懄婵挳鏌涢幇顒€绾у璺哄閺屾稓鈧綆浜堕崕鏃堟煛鐏炲墽娲撮柛鈺佸瀹曟﹢顢旀担璇℃綌缂傚倸鍊烽懗鑸垫叏闁垮绠鹃柍褜鍓氶〃銉╂倷鐎电鈷屽Δ鐘靛仦閻楃娀銆佸鈧幃鈺呭箵閹烘垹鑸归梻鍌氬€峰ù鍥ь浖閵娧呯焼濞撴埃鍋撶€规洘鍔欏畷绋课旈埀顒勬嫅閻斿吋鐓涢柛銉㈡櫅閺嬪海绱掗崜浣镐槐闁哄本鐩崺鍕礂閳哄倸鐏撮柟顔炬暬瀵挳濮€閳锯偓閹?-->
              <div class="flex-1 overflow-y-auto px-4 py-3 space-y-2 min-h-0">
                <div
                  v-for="item in pagedNotifications"
                  :key="item.id"
                  class="rounded-md border border-border bg-card px-3 py-2"
                >
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-sm font-medium">{{ item.title }}</p>
                    <span
                      v-if="!item.read"
                      class="inline-flex h-1.5 w-1.5 rounded-full bg-blue-500"
                    />
                  </div>
                  <p class="mt-1 text-xs text-muted-foreground">{{ item.content }}</p>
                  <p class="mt-2 text-[11px] text-muted-foreground/80">{{ item.time }}</p>
                </div>
                <p v-if="notifications.length === 0" class="py-8 text-center text-xs text-muted-foreground">No notifications</p>
              </div>
              <!-- 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鎯у⒔閹虫捇鈥旈崘顏佸亾閿濆簼绨奸柟鐧哥秮閺岋綁顢橀悙鎼闂傚洤顦甸弻銊モ攽閸♀晜效婵炲瓨鍤庨崐婵嬪蓟閵堝绾ч柟绋块娴犳潙鈹戦纭锋敾婵＄偘绮欓妴浣肝旈崨顓犲姦濡炪倖甯掗崐濠氭儗閹剧粯鐓欑紓浣靛灩閺嬫稓鐥幆褋鍋㈤柡灞炬礃缁绘稖顦查悗姘煎墴瀵悂骞嬮敂瑙ｆ嫼闂佸憡绻傜€氼剟寮冲▎鎾寸厽婵°倐鍋撴俊顐ｇ〒閸掓帗绻濆顒€鍞ㄩ梺闈浤涢崪浣告櫗闂佽娴烽幊鎾寸珶婵犲洤绐楅柡鍥╁Ь婵啿鈹戦悩瀹犲缂佺姵宀搁弻锝夊棘閸喗鍊梺鎶芥敱閸ㄥ灝顫忔繝姘唶闁绘柨澧庣换浣糕攽閳ュ啿绾ч柟顔煎€垮璇测槈閵忊€充簽婵炶揪绲介幗婊勭閳轰緡娓婚柕鍫濈凹缁ㄥ鏌涢悤浣哥仯缂侇喖顑夐獮鎺楀棘閸濆嫪澹曢梺鎸庣箓缁ㄨ偐鑺辨禒瀣厽闁挎繂妫欓妵婵囨叏婵犲啯銇濇俊顐㈠暙閳藉顫濇潏鈺傛緰闂傚倷鑳堕…鍫ユ晝閵夆晜鍋嬮柣妯垮皺閺嗭箓鏌熸潏鍓х暠缁炬儳銈搁弻锝夊箛椤栨氨姣㈠銈嗘⒐閸旀瑩寮婚埄鍐ㄧ窞濠电姴瀚。鐑樼節閳封偓閸涱喗鐝紓渚囧枟濡啫鐣峰鍕闁惧繒娅㈢槐鏌ユ⒑閸濆嫷妲搁柣妤€鍟村鎻掝煥閸繃杈堝銈嗗笂閻掞箓宕ｈ箛鎾斀闁绘ɑ褰冮顐︽偨椤栨稓娲撮柡宀€鍠庨悾锟犳偋閸繃鐣婚柣搴ゎ潐濞插繘宕濆鍥ㄥ床婵犻潧顑呯粈鍐煏婵炲灝鍔氭い銉﹀笚缁绘繄鍠婃径宀€锛熼梺绋款儐閸ㄥ灝鐣烽幇顖ｆЬ缂備浇椴搁幐鎼侊綖濠靛牊宕夐柧蹇氼嚃閺€銊╂⒒娴ｅ憡鍟為柛鏃€顭囨禍绋库枎閹捐櫕杈堥梺鎸庢⒒閺咁偆绮婚崜褉鍋撻悷鏉款棌闁哥姵娲滈懞杈ㄧ節濮橆厸鎷洪梺鍛婎殘閸嬬偤宕板鈧弻锛勪沪閻愵剛顦ㄩ悗鍨緲鐎氭澘鐣烽悡搴樻斀闁糕剝銇呴幋锔解拻濞达絽鎲￠幆鍫ユ煠濞茶鐏﹂柟顔ㄥ洤绠婚柟棰佺劍缂嶅骸鈹戦悙鍙夆枙濞存粍绮岄蹇撯攽閸″繑鏂€闂佺粯蓱瑜板啴顢旈妶鍡曠箚闁圭粯甯炴晶锔芥叏婵犲懏顏犻柍褜鍓涘▍銏ゆ⒔閸曨偒鐔嗘俊顖滅帛閸欏繘鏌涘畝鈧崑鐐烘偂濞嗘劑浜滈柡鍐ｅ亾闁荤噦缍佸畷鎰旈崨顔间痪闂侀€炲苯澧存慨濠冩そ閹兘骞嶉鏄忔闂備礁鎽滈崰宥夊础閸愯尙鏆︽い鎺戝閸嬨劑鏌涘☉姗堝姛闁告ü绮欏铏圭磼濮楀棛鍔搁悗瑙勬礈閺佺危閹扮増鍋嬮柛顐犲灮椤旀洟姊洪崨濠勭煀闁哥喐澹嗙划娆愮節濮橆厾鍘搁梺鍛婁緱閸橀箖宕洪敐鍥ｅ亾濞堝灝鏋熼柟姝屾珪閹便劑鍩€椤掑嫭鐓ユ繛鎴灻鈺傤殽閻愯尙澧︽慨濠勭帛閹峰懘宕ㄦ繝鍐ㄥ壍闂備礁鎽滈崰鎾寸箾閳ь剛鈧娲橀崹鍧楃嵁濡皷鍋撳☉娅亜顕ｉ崹顔规斀闁宠棄妫楅悘锝嗐亜椤撶偟澧涢柟渚垮姂瀹曟帡鎮欑€电骞堥梻浣哥枃椤宕曢搹顐ゎ洸闁绘劦鍏涚换鍡涙煟閹板吀绨婚柍褜鍓氶悧婊堝极椤曗偓楠炴帒螖閳ь剛澹曢崷顓熷枑闁绘鐗嗙粭鎺撴叏鐟欏嫮鍙€闁哄苯绉靛顏堝箥椤旇法鐛ラ梻浣虹帛閺屻劌螞濞戙垹绠熼柛娑橈攻閸庣喖鏌曟繝蹇曞矝闁稿鎹囧畷姗€顢欓悡搴ｇ崺闂備浇顫夐鏍窗閺囩姷纾鹃柡鍥ュ灪閳锋帡鏌涚仦鍓ф噮妞わ讣绠撻弻鐔烘嫚瑜忕弧鈧悗瑙勬礃缁诲牓寮崘顔肩＜婵浜畷鍫曟⒒娴ｅ憡鎯堢紒瀣╃窔瀹曘垽鎮剧仦绋夸壕婵﹩鍓氶崵鍥煛瀹€瀣М鐎殿噮鍓熷畷褰掝敊閽樺鍋撻鐐粹拺缂備焦蓱鐏忣參鏌涢悢鍛婂唉鐎殿喖顭峰鎾偄妞嬪海鐛繝鐢靛仦閸ㄨ泛顫濋妸鈺佹辈闁绘ê纾弧鈧梺鍐茬殱閸嬫捇鎮橀悙鍨珪濞寸姵鎮傚娲传閸曨剚鎷辩紓浣割儐閸ㄥ潡鏁愰悙娴嬫斀閻庯絽鐏氶弲銏＄節閵忥絾纭鹃柨鏇樺€栫粩鐔告償閵婏腹鎷绘繛杈剧到閹诧繝骞嗛崼銉︾厸闁割偒鍋勬晶鎵磼椤旂晫鎳囨鐐差儔閺佸啴鍩€椤掑嫭鍋傞柍銉﹀墯閻斿棝鎮规潪鎷岊劅闁绘搩鍓氱换娑氱箔閸濆嫬顫囬梺鍝勬湰閻╊垶宕洪崟顖氱闁绘劦鍓涢弳锔戒繆閻愵亜鈧牠寮婚妸褏鐭撶憸鐗堝笒閽冪喖鏌ㄥ┑鍡橆棡闁稿海鍠栭弻鏇㈠醇濠靛棭鍔夌紓鍌氱Т閻楀棝鍩為幋锔藉€峰Λ鐗堢箓濞堟繈姊婚崒姘仼閻庢凹鍠氶崚鎺斺偓锝庝憾閸氬顭跨捄渚剰闁逞屽墰閸忔﹢寮诲☉鈶┾偓锕傚箣濠靛懓鍩呮繝鐢靛仩閸嬫劙宕伴弽褜娼栭柧蹇氼潐閸犲棝鏌涢弴銊ヤ簻濠殿喓鍨藉铏光偓鐧搁檮濠㈡ɑ淇婃禒瀣厱闁圭儤鍩婇崝鐔兼煃瑜滈崜鐔奉焽瑜旈獮妤€顭ㄩ崨顓ф婵犻潧鍊搁幉锟犲磹閻㈠憡鐓ユ繝闈涙椤庢顨ラ悙鎼畼闁汇儺浜、姗€鎮欏顔芥缂傚倷娴囨ご鍝ユ暜濡も偓椤曘儵宕熼瀣枛閹粌螣閻撳海绉垫繝鐢靛У椤旀牠宕伴弽顓熸櫇闁靛鍎哄〒濠氭煢濡警妲洪柡鍡畵閺屾洘绻濊箛鎿冩喘缂備讲妾ч崑鎾绘⒑閻熸澘鎮戦柣锝庝邯瀹曡绻濆顒佽緢闂侀潧顦弲婊堝煕閹烘嚚褰掓晲閸涱喖鏆堥梺鐟板级閹倿寮诲☉銏″亹闁哄被鍎洪埀顒侇殕閵囧嫰顢橀悙鏉戞灎闂佽桨鐒﹂幑鍥箖閳哄懏鍤戞い鎺戝€瑰В鍥⒒閸屾瑦绁版い鏇熺墵瀹曡鎯旈妸銉ョ獩濡炪倖姊婚弲顐﹀级濞差亝鈷掗柛灞剧懅椤︼妇绱撳鍜冭含鐎殿喓鍔戝畷锟犳倻閸℃绋侀梻浣藉吹閸犳劗鈧艾鐗嗛埥澶愬閻樻妲伴梻渚€娼ц噹闁告洦鍓﹂崯搴ㄦ⒒閸屾瑧绐旀繛浣冲棗顤傞梻浣告惈閹冲寮查悩宸殨妞ゆ劧绠戦悙濠冦亜閹哄秷鍏岄柛姗€浜跺娲濞戣鲸鈻撻梺鎼炲妼绾绢厾鍒掑▎鎴犵＜婵☆垵鍋愰鏇㈡⒑閸涘﹣绶遍柛娆忕箻閻擃剟顢楅崟顒傚幐閻庡厜鍋撻悗锝庡墰閿涚喐绻涚€电顎撶紒鐘虫崌楠炲啴宕滆濞岊亝绻濋崹顐ｅ暗缂佸宕电槐鎺旂磼濡鈧帡鏌涢悩璇ц含鐎规洩绲介～婊堝焵椤掑嫬纾绘俊銈傚亾閾绘牠鏌ｅ鈧褎绂掑鍛＜濠㈣泛锕︾粔娲煏閸℃洜顦︽い顐ｇ箘閹瑰嫰宕崟顓犲春濠碉紕鍋戦崐鏍几椤曗偓瀹曠喖顢橀悩闈涘笌闂傚倷绀侀悿鍥綖婢舵劕鍨傞柛褎顨呯粻鏍煃閸濆嫭鍣圭紒鐘崇☉闇夐柨婵嗘噺閸熺偞绻涢崨顔炬创婵﹦绮幏鍛村川婵犲啫鏋戝┑鐘愁問閸犳岸寮繝姘卞祦闁硅揪绠戦悙濠勬喐韫囨稑姹查柨鏇炲€归悡娆撴⒑椤撱劎鐣遍柛妯绘尦閺岋繝鍩€椤掍胶顩烽悗锝庡亜閳ь剛鏁婚弻銊モ攽閸℃瑥鍤紓浣靛妺缁瑩寮婚敐澶嬫櫜闁告侗鍠楅崕鎾绘⒑鐎圭媭娼愰柛銊ョ埣閻涱喗绻濋崶銊у幈婵犵數濮撮崯顖滅矆鐎ｎ兘鍋撶憴鍕闁搞劌鐖奸妴浣糕槈閵忊€斥偓鐑芥煠绾板崬澧扮€规洖鐖煎缁樻媴閾忓箍鈧﹪鏌涢幘瀵哥畼缂侇喗鐟╅獮鎺懳旀担闀愮暗闂備礁鎼ú銏ゅ垂濞差亝鍋傛繛鎴欏灪閻撴洟鏌曟径娑氬埌闁告梹鑹鹃埞鎴﹀灳閸愬弶鍊銈冨妸閸庣敻骞冨▎鎾崇妞ゆ挾鍠撻弶褰掓⒒娴ｅ憡鎯堥柣顒€銈稿畷浼村冀瑜忛弳锕傛煥濠靛棙顥滅紒鍓佸仱閹﹢鎮欓弶鎴濆Б濠电偛鎳忓畝绋款潖缂佹ɑ濯撮柛娑橈攻閸庢捇姊哄ú璇插箹妞わ箒浜Σ鎰版倷閸濆嫮鍔﹀銈嗗笒閸婅崵澹曟總鍛婄厽婵☆垵娅ｉ敍宥嗙箾閹绘帞鎽犳い銊ｅ劦閹瑩骞栭鐘插Ш闂備線鈧偛鑻晶瀛樼箾娴ｅ啿瀚悵璺衡攽閻樿弓绱栭柧蹇氼潐瀹曞鎮跺☉鎺戝⒉闁哄倵鍋撻梻鍌欒兌缁垶宕濆Ο闂寸剨婵炲棙鎸哥粻娲煟濡吋鏆╃痪鎯у悑閵囧嫰寮埀顒勫磿閾忣偆澧＄紓鍌氬€风粈渚€宕愰崫銉х煋鐟滅増甯囬埀顑跨窔瀵噣宕煎┑瀣暪婵?+ 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閹冣挃闁硅櫕鎹囬垾鏃堝礃椤忎礁浜鹃柨婵嗙凹缁ㄥジ鏌熼惂鍝ョМ闁哄矉缍侀、姗€鎮欓幖顓燁棧闂備線娼уΛ娆戞暜閹烘缍栨繝闈涱儐閺呮煡鏌涘☉鍗炲妞ゃ儲鑹鹃埞鎴炲箠闁稿﹥顨嗛幈銊╂倻閽樺锛涘┑鐐村灍閹崇偤宕堕浣镐缓缂備礁顑嗙€笛囨倵椤掑嫭鍊垫鐐茬仢閸旀碍銇勯敂璇茬仯缂侇喖鐗忛埀顒婄秵閸嬩焦绂嶅鍫熺厵闁告繂瀚倴闂佸憡鏌ㄧ粔鐢稿Φ閸曨垰妫橀柟绋块閺嬬姴鈹戦纭峰姛缂侇噮鍨堕獮蹇涘川閺夋垵绐涙繝鐢靛Т閹虫劙銆侀崨瀛樷拻濞达絼璀﹂悞鍓х磼閵婏附銇濈€规洘鍔曢埞鎴﹀幢濞嗘劖顔曢梻浣圭湽閸ㄥ綊骞夐敓鐘茬柧婵犻潧顑嗛悡鍐喐濠婂牆绀堥柣鏃傚帶閺勩儵鏌曟径娑氱暠缂佸墎鍋涢埞鎴︽倷椤忓嫮浼勯梺鍝ュУ閻楃姴顕ｆ繝姘╃憸澶愬磻閹剧粯鏅查幖绮光偓鑼嚬婵犵數濮伴崹娲垂閸噮娼栫紓浣股戞刊瀵哥磼濞戞﹩鍎忔繛鍫弮濮婃椽宕ㄦ繝鍌滀患闂佸搫鎷嬮崑鍡椢ｉ幇鐗堝€烽柛婵嗗閼板灝鈹戦悙鏉戠仸妞ゎ厼娲畷?-->
              <div class="border-t border-border px-3 py-2 shrink-0 flex items-center justify-between">
                <Button
                  variant="ghost"
                  size="sm"
                  class="h-7 cursor-pointer text-xs"
                  @click="markAllNotificationsRead"
                >
                  闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鏁愭径濠勵吅闂佹寧绻傞幉娑㈠箻缂佹鍘遍梺闈涚墕閹冲酣顢旈銏＄厸閻忕偛澧藉ú瀛樸亜閵忊剝绀嬮柡浣瑰姍瀹曞崬鈻庡▎鎴犫敍闂傚倸鍊风欢姘跺焵椤掑倸浠滈柤娲诲灡閺呭爼宕滆绾惧ジ鏌ｅΟ鎸庣彧閻忓浚鍙冮弻锝夋晲婢跺鏆犵紓浣芥閺咁偆鍒掑▎蹇婃瀻闁绘劦鍓涚粔閬嶆⒒閸屾瑨鍏岄柛瀣ㄥ姂瀹曟洟鏌嗗鍛焾闁荤姵浜介崝蹇旀叏閹惰姤鐓忓璺烘濞呭棝鏌嶉柨瀣瑨闂囧鏌ㄥ┑鍡樼ォ闁绘帞鍋撻妵鍕Ψ閵壯咁啋闂佸搫鏈粙鎾诲焵椤掑﹦宀涢柡鍛箘缁綁寮崒妤€浜鹃悷娆忓缁€鍐╃箾閸欏顏堚€﹂崶顏嗙杸婵炴垶顭囬崢鎼佹⒑閸涘﹤濮﹀ù婊呭仱瀹曟繄鎹勭悰鈩冩杸闂佺粯锕╅崰鏍倶闁秵鐓曢柍鍝勫€绘晶鐢碘偓瑙勬礃缁诲牆顕ｆ禒瀣垫晣闁绘棁娓圭花鍨節閻㈤潧浠滄俊顐ｇ懇楠炴劙宕妷褎锛忛悷婊勬瀵鈽夐姀鈺傛櫇闂佹寧绻傚ú銊╂偩閻㈠憡鈷戦柟鎯板Г閺佽鲸淇婇銏犳殻鐎殿喖顭烽弫鎰緞鐎ｎ偅鐝抽梻浣稿閸嬪懐鍒掑畝鍕畾闁割偁鍎查埛鎴炴叏閻熺増鎼愰柛鏃€娼欓湁婵犲﹤绨奸柇顖炴煟濞戝崬娅嶇€规洖宕～婵嬪礂婢惰浜缁樻媴娓氼垳鍔稿銈嗗灥閸熸潙鐣烽弴銏″仺缂佸鍎婚幗鏇㈡⒑閹稿海鈽夐悗姘间簻閳讳粙顢旈崱娆戯紲闁诲函缍嗘禍鐐寸閵忋倖鐓冪€瑰嫰鍋婂Ο鈧梺璇″枟椤ㄥ﹤鐣疯ぐ鎺濇晝闁挎繂娲ら崵鎺楁⒑鐠囨彃顒㈤柛鎴濈秺瀹曟娊鏁愭径濠冩К闂侀€炲苯澧柕鍥у楠炴帡骞嬮姘潬缂傚倷绀侀ˇ闈涱焽瑜斿﹢浣糕攽閻樿宸ラ柟鍐插缁傛帗娼忛埞鎯т壕閻熸瑥瀚粈鍐磼鐠囪尙澧﹂柣娑卞櫍瀵粙濡搁敃鈧鎾绘⒑缁嬭法绠版い锔藉閳ь剚鑹鹃妶绋款潖缂佹ɑ濯撮柛娑橈工閺嗗牏绱撴担鍛婃儓婵炲皷鈧磭鏆﹂柡鍥ュ灪閻掕偐鈧箍鍎遍幊搴ㄥ吹閹达附鐓欓柛蹇氬亹閺嗘﹢鏌涢弬璺ㄐч柟顔光偓鏂ユ瀻闁规儳顕崣鍕椤愩垺绁紒鑼跺Г缁傚秵銈ｉ崘鈺冨幘闂佺懓鍢查張顒傛兜閸洘鐓冪憸婊堝礈濮橀鏁婇柡宥庡幖缁愭鏌″搴″箰闁逞屽墾缁犳捇寮婚妸褉鍋撻敐鍌涙珖缂佺姵宀稿娲礈閹绘帊绨煎┑鐐插级閻楃娀鎮伴鈧慨鈧柨娑樺椤旀洟姊虹化鏇炲⒉閽冮亶鎮樿箛鏇烆暭闁靛洤瀚幆鏃堟晬閸曟嚪鍕弿濠电姴瀚敮娑㈡煙瀹勭増鍤囩€规洏鍔嶇换婵嬪磼濞戞瑧鏆梻鍌氬€烽懗鍫曞箠閹捐绠烘繝濠傜墐閳ь剨绠撳畷濂稿Ψ椤旇姤娅旈梻浣瑰缁诲倸煤閿曗偓閻ｉ攱寰勬繛搴撳亾閹烘埈娼╅柣鎾虫捣娴狀垶姊洪崫銉ヤ户闁轰浇顕ч～蹇撁洪鍛画闂佸搫顦花閬嶅箰閸愵亞纾藉〒姘搐濞呮﹢鏌涢妸銉у煟鐎?
                </Button>
                <div v-if="notifTotalPages > 1" class="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-6 w-6 cursor-pointer"
                    :disabled="notifPage === 1"
                    @click="notifPage--"
                  >
                    <ChevronLeftIcon class="size-3" />
                  </Button>
                  <span class="text-xs text-muted-foreground tabular-nums">{{ notifPage }} / {{ notifTotalPages }}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-6 w-6 cursor-pointer"
                    :disabled="notifPage === notifTotalPages"
                    @click="notifPage++"
                  >
                    <ChevronRight class="size-3" />
                  </Button>
                </div>
                <span v-else class="text-xs text-muted-foreground tabular-nums">{{ notifications.length }} items</span>
              </div>
            </SheetContent>
          </Sheet>

          <Button
            variant="ghost"
            size="icon"
            class="cursor-pointer text-muted-foreground"
            @click="goToSettings"
          >
            <Settings class="size-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            class="cursor-pointer text-muted-foreground"
            @click="toggleTheme"
          >
            <Moon v-if="isDarkMode" class="size-4" />
            <Sun v-else class="size-4" />
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="ghost" size="icon" class="relative cursor-pointer text-muted-foreground">
                <Avatar class="size-8">
                  <AvatarFallback class="bg-primary/10 text-xs text-primary">
                    {{ username.charAt(0).toUpperCase() }}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" class="w-56">
              <DropdownMenuLabel>
                <div class="flex items-center justify-between">
                  <span class="text-sm text-foreground">{{ username }}</span>
                  <Badge :variant="roleBadgeVariant">{{ roleText }}</Badge>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem class="cursor-pointer" @click="goToProfile">
                <UserRound class="mr-2 size-4" />
                闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鏁愭径濠勵吅闂佹寧绻傞幉娑㈠箻缂佹鍘辨繝鐢靛Т閸婂綊宕戦妷鈺傜厸閻忕偠顕ф慨鍌溾偓娈垮枟濞兼瑨鐏冮梺閫炲苯澧紒鍌氱Ч楠炲棜顧佹繛鎾愁煼閺屾洟宕煎┑鍫濆毈缂備降鍔岄…鐑藉蓟濞戙垺鍋勯柛娑橈功缁嬪洭姊烘导娆戞偧闁哄苯顦垫俊鐢稿箛閺夎法顔婂┑鐘绘涧濞诧箑鈻嶉弮鍫熲拻濞达絽鎲￠崯鐐层€掑顓ф疁鐎规洖缍婇幃褔宕奸悢宄颁紟婵犵數鍋涘Ο濠冪濠靛鐓曢柟鐑樺殮瑜版帗鏅查柛鏇ㄥ櫘閸斿懎鈹戦悙鎻掓倯閻㈩垽绻濆璇测槈閵忕姴宓嗛梺缁樺姇閸氣偓缂侇喚鏁诲鐑樺濞嗘垵鍩屾繝鈷€鍐╂崳婵″弶鍔欓獮妯尖偓娑櫭鎾绘⒑閸︻厾甯涢悽顖氾攻缁旂喖寮撮悙鈺傛杸闂佺粯锕╅崰鏍倶鏉堛劎绠惧璺侯儑閳洜鈧灚婢樼€氭澘鐣烽崼鏇ㄦ晢闁逞屽墰婢规洘绻濆顓犲幍闂佺顫夐崝鏇㈠触閸︻厸鍋撶憴鍕矮缂佽埖宀稿璇测槈閳垛斁鍋撻敃鍌氱婵犻潧娲ㄦ禍顏勨攽閻樻剚鍟忛柛鐘崇墬椤ㄣ儵骞栨担娴嬪亾閺冨牆绀冩い鏂挎瑜旈悡顐﹀炊閵婏箑鏆楀┑陇顕滅紞浣割潖濞差亜绠归柣鎰絻椤懎鈹戦悙宸Ч闁烩晩鍨堕妴浣割潩閼稿灚娅滈梺绯曞墲椤ㄥ繘宕甸妶澶嬧拺闁告繂瀚峰Σ褰掓煕閵堝繒鐣靛┑鈩冩倐閸╋繝宕掑鍐ㄦ辈闂傚倷绀侀幖顐﹀磹閹间焦鍊舵繝闈涱儏閻撴洟鏌￠崘锝呬壕闂侀潧娲ょ€氭澘顕ｉ鈧崺鈧い鎺嗗亾閻撱倝鏌ｉ弬娆炬疇婵炲吋鐗楃换娑橆啅椤旇崵鍑归梺绋款儜缁绘繂顫忓ú顏嶆晣闁靛ě鍛婵犵數鍋涢悧鍡涙偉閻撳寒娼栭柧蹇撴贡閻瑦绻涢崱妯哄姢闁告挻濞婂娲传閵夈儛锝夋煟濡ゅ啫鈻堥柟顔诲嵆椤㈡瑩鎮惧畝鈧惁鍫ユ⒑閹肩偛鍔€闁告劦浜炲畷娲⒒娴ｇ瓔鍤欓悗娑掓櫇缁瑩骞掑鐑╁亾閿曞倸鐐婃い鎺嗗亾闁稿被鍔戦弻鐔煎箚瑜嶉。宕囩棯閸欍儳鐭欓柡灞剧〒娴狅箓宕滆閸ｎ噣姊洪崨濠冪叆缂佸缍婇獮蹇涘箣閿旂晫鍔堕悗骞垮劚濡盯宕㈤幘缁樷拻濞达絽鎽滄禒銏°亜閹存繃鍣洪柟渚垮妼椤撳吋寰勭€ｎ剙骞愰梺璇茬箳閸嬬喖宕戦幘鍓佺焼閻庯綆鍏橀崑鎾舵喆閸曨剛顦ㄩ梺绋块閵堟瓕妫熼梺鍛婄懃椤︻厽绂嶅鍫㈠彄闁搞儵顥撻崚鐗堫殽閻愭惌娈曢柕鍥у婵℃悂鏁愰崨顓炐曢梻浣筋嚃閸犳鎮烽埡鍛祦闁哄稁鍙庨弫鍥煟濡绲诲Δ鏃堟⒒閸屾艾鈧绮堟担闈╄€块梺顒€绉寸粻鐘绘煙閹呬邯闁稿鎸搁～婵嬫偂鎼达紕顔愭俊鐐€ら崢鐓幟洪顫偓渚€寮崼婵嬪敹闂佺粯妫佸〒鍦磾閺囥垺鈷掑ù锝囶焾椤ュ繘鏌涚€ｎ亝鍣介柟骞垮灲瀹曠喖顢涘顒€浜堕梻浣告啞椤ㄥ牓宕戦幇鏉跨哗?
              </DropdownMenuItem>
              <DropdownMenuItem class="cursor-pointer" @click="goToSettings">
                <Settings class="mr-2 size-4" />
                缂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁诡垎鍐ｆ寖闂佺娅曢幑鍥灳閺冨牆绀冩い蹇庣娴滈箖鏌ㄥ┑鍡欏嚬缂併劎绮妵鍕箳鐎ｎ亞浠鹃梺闈涙搐鐎氫即鐛崶顒夋晜闁糕剝鐟ч崢顖炴⒒娴ｅ憡鎯堥悶姘煎亰瀹曟繈骞嬮敃鈧粻鏍煏韫囧鈧洘瀵奸悩缁樼厱闁哄洨鍠庨悘鐔兼煕閵娿倗鐭欑€殿喛顕ч埥澶愬閻樻牑鏅犻弻鏇熷緞閸繂濮夐梺绋款儐閹瑰洤鐣疯ぐ鎺濇晪闁告侗鍠氱粙浣糕攽閻樺灚鏆╁┑顔炬暬閹虫繃銈ｉ崘鈺冨帒闂佹悶鍎洪崜姘舵偂閻斿吋鐓涢柛鎰剁到娴滅偓绻涚€涙鐭嗙紒顔界懇瀹曟椽鍩€椤掍降浜滈柟鍝勭Ф椤︼附绻涢幖顓炴珝闁哄备鈧磭鏆嗛悗锝庡墰閻﹀牓鎮楃憴鍕濞存粌鐖奸妴浣割潨閳ь剟骞冮埡鍛瀭妞ゆ劧缍嗛崯宀勬⒒閸屾艾鈧绮堟笟鈧獮鏍敃閿旇棄鍓规繝銏ｆ硾閻偐绮堟繝鍋綊鏁愰崼顐ｇ秷闂佸憡鐟ョ换姗€寮诲鍫闂佸憡鎸鹃崰鏍ь嚕婵犳艾鍗抽柕蹇曞█閸炶泛鈹戦悩缁樻锭婵炴潙鍊歌灋闁跨喓濮甸埛鎺懨归敐鍫殐闁稿簺鍎甸弻娑樷枎韫囨挻娈銈庡亜缁绘劗鍙呭銈呯箰鐎氼噣顢欓幇鐗堚拺缂備焦锚婵牏鎲搁弶鍨殻闁炽儲鐗楀鍕暆閳ь剛澹曢挊澹濆綊鏁愰崶鈺傛啒闂佹悶鍊栭悷鈺呭蓟閿濆憘鏃€鎷呴悷鎵暡婵＄偑鍊栧ú鈺冪礊娴ｅ壊鍤曢柟宄扮灱閻も偓闂佹寧绻傚Λ宀勫几閸℃瑧纾介柛灞捐壘閳ь剛鍏橀幊妤呮嚋閸偄寮块梺姹囧灮閺佹悂鎯屽▎鎾寸厵閺夊牊宕橀铏圭磽瀹ュ棛澧紒缁樼箞濡啫鈽夐崡鐐插缂傚倷璁查崑鎾绘煕瀹€鈧崑鐐烘偂閻樺磭绠鹃柡澶嬪焾閸庢劖绻涢崨顓熷枠鐎规洦鍨崇划娆愭償閹惧瓨鏉搁梻浣虹帛閿氶柣蹇斿哺瀵娊鍩℃担鍙夋杸濡炪倖姊婚崑鎾诲汲椤掍降浜滈柕蹇ョ磿閹冲洨鈧鍠曠划娆撱€佸鈧幃娆撴嚑椤戣棄浜炬い鎾跺枔缁犻箖鏌℃径瀣仴闁诡喗鍨剁换娑㈠礂閼测晜鍣у┑鐐村絻濞尖€愁潖缂佹ɑ濯撮柛婵勫劤妤旀繝纰樻閸嬪鈻旈弴鐘插灊闁割偆鍠撻悷褰掓煃瑜滈崜鐔肩嵁韫囨稑绠ｉ柨鏃囨娴滄粓姊洪崨濠勭細闁稿孩濞婇、娆撳即閵忊檧鎷洪梺鑽ゅ枑婢瑰棝骞楅悩缁樼厽闁绘梹娼欓崝锕傛煙椤旀枻鑰块柛鈺嬬節瀹曟﹢顢旈崱顓犲簥闂傚倷鑳剁划顖炩€﹂崶顒€鏋侀柛婵勫劜閺嗘粍绻涢幋鐐偓鎺撴償閵娿儳鍊為悷婊勭箞閻擃剟顢楅埀顒勫煘閹达箑鐏崇€规洖娲ら悡鐔兼倵鐟欏嫭绀冮悽顖涘浮閿濈偛鈹戠€ｅ灚鏅濋梺闈涚箚閺呮粓藟閿熺姵鈷掗柛灞捐壘閳ь剚鎮傚畷鎰版倻閼恒儱娈戦梺鍓插亝濞叉牜绮婚悩缁樼厵闁硅鍔﹂崵娆撴煟閵堝骸娅嶉柟顔肩秺楠炰線骞掗幋婵愮€撮柣搴ゎ潐濞叉牕顕ｉ崼鏇炵疄闁靛鍎哄〒濠氭偣閸ヮ亜绱﹀瑙勬礃娣?
              </DropdownMenuItem>
              <DropdownMenuItem class="cursor-pointer" @click="goToSecuritySettings">
                <ShieldAlert class="mr-2 size-4" />
                闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤濠€閬嶅焵椤掑倹鍤€閻庢凹鍙冨畷宕囧鐎ｃ劋姹楅梺鍦劋閸ㄥ綊宕愰悙宸富闁靛牆妫楃粭鎺撱亜閿斿灝宓嗙€殿喗鐓￠、鏃堝醇閻旇渹鐢绘繝鐢靛Т閿曘倝宕悧鍫熸珡濠电姷鏁告慨顓㈠磻閹剧偨鈧帒顫濋敐鍛婵犳鍠栭敃銊モ枍閿濆洦顫曢柟鐑樺殾閻斿吋鎯為梺顐ｇ〒缁€鍐ㄢ攽閻樻鏆俊鎻掓嚇瀹曟垿宕熼娑樹壕婵鍘ч弸銈夋煕閹烘挸绗氱紒缁樼箓椤繈顢橀悙鐗堢潖缂傚倸鍊搁崐鐑芥倿閿曞倵鈧箓宕堕鈧崒銊╂煟閵忕姵鍟為柍閿嬪灴閹綊宕堕敐鍌氫壕鐎规洖娲犻崑鎾寸節濮橆厾鍘遍梺纭呭焽閸斿秴鈻嶉幘缁樼厱闁绘棃顥撴晶锔芥叏婵犲嫮甯涢柟宄版噽閹叉挳宕熼鈥虫憢闂傚倷鑳堕…鍫⑩偓娑掓櫅椤啴鎸婃径灞炬濠电姴锕ら悧濠囧疾濠靛鐓曢悘鐐插⒔椤ｆ煡鏌ｆ惔顔煎⒋闁诡喗顨婇悰顕€宕归鐓庮潛婵＄偑鍊х紓姘跺础閹惰棄绠栭柨鐔哄У閸嬪嫰鏌涜箛姘汗闁告鏁诲缁樼瑹閸パ冧紟缂備胶濮甸崹鍧楀箖濮椻偓閹晝绱掑Ο鐓庡箺闂備線娼ч…顓㈡⒔閸曨垰桅婵犻潧顑嗛悡娑氣偓鍏夊亾閻庯綆鍓涜ⅵ婵°倗濮烽崑鐐烘晝閵忕媭鍤曢柛顐ｆ礀缁狅綁鏌ｅΟ澶稿惈缂佲偓婢跺ň鏀介柣妯活問閺嗩垱淇婇幓鎺撳殗鐎规洘鍨垮畷鐔碱敍濮樿京鏋冩繝娈垮枟閵囨盯宕戦幘缁樼厪闁糕剝娲滅粣鏃傗偓娈垮枟閹歌櫕鎱ㄩ埀顒勬煟濞嗗苯浜惧┑鐐靛帶閿曨亜顫忓ú顏呭€烽柦妯侯槸婵洟姊洪崨濠冨鞍闁艰鍎冲畵鍕煛婢跺﹦澧戦柛鏂挎捣瀵囧焵椤掑嫭鈷戞慨鐟版搐閻忓弶绻涙担鍐插椤╅攱绻濇繝鍌涘櫝闁稿鎸搁埢鎾诲垂椤旂晫浜堕梻浣侯焾妤犳悂濡堕幖浣哄祦婵°倕鎷嬮弫鍐煥閺冨泦鎺楀箯濞差亝鈷戦柛娑橈功閳藉鏌ㄩ弴妯衡偓妤冨垝椤撱垹绠虫俊銈勮兌閸欏棝姊洪崫鍕闁挎岸鏌涢弬璇测偓妤冩閹捐纾兼繛鎴炵懃闂夊秶绱撴担绋库偓鍦暜閻愬搫鐒垫い鎺戯功缁夐潧霉濠婂嫮鐭岀紒顕嗙到閳藉鈻庨幋鐘垫闂備焦鐪归崹钘夘焽瑜嶉悺顓㈡⒑鐠囨彃顒㈤柛鎴濈秺瀹曟粓鎮㈤崗鐓庝粧濡炪倖娲嶉崑鎾垛偓瑙勬礀閵堝憡淇婇悜鑺ユ櫆閻熸瑥瀚鐑樼節閻㈤潧浠╅柟娲讳簽瀵板﹥绂掔€ｎ亞鐤呴梺鎸庣☉鐎氼厾鈧艾顭烽弻銊╂偄閸濆嫅锝夋煟閹惧瓨绀嬮柟顔筋殜閺佹劖鎯旈垾鑼嚬闁诲氦顫夊ú鏍儗閸岀偛钃熼柡鍥ュ灩楠炪垺淇婇妶鍌氫壕闂佸搫妫寸徊鍧楀焵椤掑喚娼愭繛鎻掔箻瀹曟繈骞嬪┑鎰闂佸壊鍋呭ú鏍不閿濆鐓熸俊顖濇娴犳盯鏌ｆ惔顔兼珝婵﹤顭峰畷鎺戭潩閼测晛褰嗛梻浣侯焾椤戝懐鈧凹鍓涢崣鍛存⒑閹稿孩鐓ュ褌绮欓幆灞解枎閹惧鍘甸梺缁樺灦閿曗晛鈻撻弮鍌滄／?
              </DropdownMenuItem>
              <DropdownMenuItem v-if="role === 'admin' || role === 'operator'" class="cursor-pointer" @click="router.push('/integrations')">
                <Blocks class="mr-2 size-4" />
                闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閹冣挃闁硅櫕鎹囬垾鏃堝礃椤忎礁浜鹃柨婵嗙凹缁ㄥジ鏌熼惂鍝ョМ闁哄矉缍侀、姗€鎮欓幖顓燁棧闂傚倸娲らˇ鐢稿蓟閵娿儮鏀介柛鈾€鏅滄晥濠电偛鐡ㄩ崵搴ㄥ磹濠靛钃熼柕鍫濐槸缁狙囨煙缁嬪潡顎楀ù鐘虫尦閹鈻撻崹顔界亪闂佺粯鐗滈崢褔鎮鹃悜鑺ュ亗閹兼惌鍠楅崓闈涱渻閵堝棙灏甸柛鐘虫崄閵囨劙宕ㄧ€涙ǚ鎷绘繛杈剧秬椤宕戦悩缁樼厱闁哄倽娉曡倴闂佺懓绠嶉崹钘夌暦濮椻偓椤㈡瑩宕叉径娑氱暤闁哄本鐩鎾Ω閵壯傚摋闂備礁鎲￠崝蹇涘磻閹剧粯鈷掑〒姘ｅ亾婵炰匠鍡楁闂備礁鎲℃笟妤呭垂閹殿喗鏆滈柟鐑橆殕閳锋帡鏌涚仦鍓ф噮妞わ讣绠撻弻鐔哄枈閸楃偘绨婚柧鑽ゅ仦缁绘盯宕卞Ο铏逛淮闂佹悶鍔嶇换鍕焵椤掆偓閸樻粓宕戦幘缁樼厱闁哄洢鍔屾禍鐐烘煕濡粯灏︽慨濠呮濞戠敻宕ㄩ鍏奸敪闂傚倸鍊哥€氼剛鈧碍婢橀悾鐑藉箣閿曗偓缁犳盯鏌ｅΔ鈧悧蹇涘储閻㈢數纾介柛灞剧懅閸斿秹鏌ㄥ鑸电厱鐟滃秹鏁冮鍫濊摕婵炴垶鍩冮崑鎾绘晲鎼粹€茬凹閻庤娲栭惌鍌炲蓟閻旂⒈鏁婇柣鎰靛墯閻濐亞绱撴笟鍥ф灍闁荤啿鏅涢悾鐤亹閹烘繃鏅╅梺绋跨箳閳峰牓宕ラ崶顒佲拻闁稿本鐟ㄩ崗宀勬煙閾忣偅宕岀€规洏鍎抽埀顒婄秵閸犳宕戦埡鍌樹簻闊洦鎸炬晶鏇犵磼閳ь剚寰勭仦绋夸壕妤犵偛鐏濋崝姘亜閿斿灝宓嗙€规洘鍨垮畷鎺楁倷闂堟稑绲奸梻浣规偠閸庮垶宕濇惔銊ノラ柟鐑橆殕閻撴洘绻涢崱妯哄鐎规洖鐭傞弻锛勪沪閸撗勫垱婵犵绱曢崗姗€寮幇鏉垮窛妞ゆ挾鍎愬娑㈡⒒閸屾瑧顦﹂柟璇х節瀵鏁愭径濠勶紮濠德板€曢幊蹇涘磿婢跺浜滈煫鍥ㄦ尵婢ф洜绱掗悩铏殤闁规彃鎲￠幆鏃堝Ω閵壯嶇幢闂備線娼чˇ顐﹀疾濠婂牊鍋傛繛鎴欏灪閸婂爼鏌ｉ幇顒備粵婵炲懏娲熼幊鏍冀椤愩倗锛濇繛杈剧导缁瑩宕ú顏呭仺妞ゆ牗绋戠粭鈺呮煟韫囨柨绗掗柍瑙勫灴閹瑧鎹勯搹瑙勵嚄缂傚倷绶￠崳顕€宕归幆鐗堬紓闂備礁澹婇崑鍡涘窗瀹ュ洦宕查柛鈩冪⊕閻撳繘鏌涢锝囩畺闁瑰吋鍔欏畷顖炲箹娴ｅ厜鎷虹紓浣割儐椤戞瑩宕曢幋锔界厱閻庯絻鍔岄埀顒佺箞閻涱噣宕橀褎鈻岄柣搴㈩問閸犳骞愰幎钘夊瀭闁诡垎鍛闂佹悶鍎滈埀顒勫磻閹捐绠抽柟瀛樻⒐閺傗偓闂備焦瀵х粙鎴犫偓姘煎墯缁傚秵绺介崨濠勫幈婵犵數濮撮崯鐗堟櫠椤忓懌浜滈柡鍌濇硶缁犺尙绱掔紒妯肩畵妞ゎ偅绻堥、妤呭磼閿旀儳鑰块梻鍌氬€烽懗鍫曞箠閹惧瓨娅犻柣锝呰嫰閸ㄦ繃銇勯弽顐沪闁稿鍊块弻娑㈠箛閸忓摜鍑归梺鍝ュУ閸旀牜鎹㈠┑鍥╃瘈闁稿本绮岄。铏圭磽娴ｆ彃浜鹃梺鍓插亞閸犳劙宕ｈ箛鏂剧箚妞ゆ牗绋戦婊呯棯椤撶偛鈷旂紒杈ㄥ浮閹晠鎼归銈呭殥闂佸墽绮悧鐘诲蓟閵娿儮鏀介柛鈩兠▍锝夋⒑閸濆嫭顥為柣鐔濆懏顫曢柟鐑橆殔閻掑灚銇勯幒鎴濐仼妤犵偑鍨虹换娑㈠箣閻愬灚鍣梺鍛婎焽閺佽顫忛搹鍦＜婵☆垵娅ｆ禒鎼佹⒑閹稿孩纾甸柡鍛洴閸┿垽骞樼拠鑼潉闂佺鏈划搴ㄦ晬濠婂牊鈷戠紓浣光棨椤忓牆绠规い鎰剁畱鐟欙箓鏌涢敂璇插箻缁炬儳銈稿鍫曞醇濞戞ê顬夐柣蹇撶箣閸楁娊寮婚悢椋庢殝闁绘鐗嗗▍褔姊鸿ぐ鎺濇濠电偐鍋撻梺杞扮缁夌懓鐣烽悢纰辨晝闁虫儼锟ラ崝鎴濐潖?
              </DropdownMenuItem>
              <DropdownMenuItem v-if="role === 'admin'" class="cursor-pointer" @click="router.push('/observability')">
                <Activity class="mr-2 size-4" />
                缂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁诡垎鍐ｆ寖闂佺娅曢幑鍥灳閺冨牆绀冩い蹇庣娴滈箖鏌ㄥ┑鍡欏嚬缂併劎绮妵鍕箳鐎ｎ亞浠鹃梺闈涙搐鐎氫即鐛崶顒夋晜闁糕剝鐟ч崢顖炴⒒娴ｅ憡鎯堥悶姘煎亰瀹曟繈骞嬮敃鈧粻鏍煏韫囧鈧洘瀵奸悩缁樼厱闁哄洨鍠庨悘鐔兼煕閵娿倗鐭欑€殿喛顕ч埥澶愬閻樻牑鏅犻弻鏇熷緞閸繂濮夐梺绋款儐閹瑰洤鐣疯ぐ鎺濇晪闁告侗鍠氱粙浣糕攽閻樺灚鏆╁┑顔炬暬閹虫繃銈ｉ崘鈺冨帒闂佹悶鍎洪崜姘舵偂閻斿吋鐓涢柛鎰剁到娴滅偓绻涚€涙鐭嗙紒顔界懇瀹曟椽鍩€椤掍降浜滈柟鍝勭Ф椤︼附绻涢幖顓炴珝闁哄备鈧磭鏆嗛悗锝庡墰閻﹀牓鎮楃憴鍕濞存粌鐖奸妴浣割潨閳ь剟骞冮埡鍛瀭妞ゆ劧缍嗛崯宀勬⒒閸屾艾鈧绮堟笟鈧獮鏍敃閿旇棄鍓规繝銏ｆ硾閻偐绮堟繝鍋綊鏁愰崼顐ｇ秷闂佸憡鐟ョ换姗€寮诲鍫闂佸憡鎸鹃崰鏍ь嚕婵犳艾鍗抽柕蹇曞█閸炶泛鈹戦悩缁樻锭婵炴潙鍊歌灋闁跨喓濮甸埛鎺懨归敐鍫殐闁稿簺鍎甸弻娑樷枎韫囨挻娈銈庡亜缁绘劗鍙呭銈呯箰鐎氼噣顢欓幇鐗堚拺缂備焦锚婵牏鎲搁弶鍨殻闁炽儲鐗楀鍕暆閳ь剛澹曢挊澹濆綊鏁愰崶鈺傛啒闂佹悶鍊栭悷鈺呭蓟濞戙垺鍋勯悹鍝勬惈缁侇喖螖閻橀潧浠﹂柛銊﹀閹便劑鍩€椤掑嫭鐓熸慨妤€妫楁禍婵囥亜椤愩垻孝闁宠鍨块、娆戠驳鐎ｎ偆鏆ユ繝纰樻閸嬪懘銆冩繝鍌ゅ殨闁哄被鍎查崑鎰偓鐟板閸犳鈧潧鐭傚娲濞戞艾顣哄┑鈽嗗亝閻熲晞妫㈤梺绯曞墲閻熴垽宕戦幘鑸靛枂闁告洦鍓涢ˇ顓㈡⒑鏉炴壆顦︽い顓犲厴閻涱噣宕卞☉妯碱槹濡炪倖甯婄粈渚€宕濋崨瀛樷拺闂傚牊渚楅悡顓㈡煠闂堟稓绉烘鐐茬箻瀹曨偊宕熼妸锔芥澑闂備胶绮崝妯衡枖濞戙垺瀚婇柛蹇曨儠娴滄粓鏌￠崶褎顥滄繛灞傚妼閻ｅ灚鎷呴柅娑氱畾闂侀潧鐗嗙€氭澘顬婂畡鎳婄懓顭ㄩ崟顓犵厜闂佸搫鏈ú妯兼崲濞戙垹鍨傛い鏃傚帶椤碍淇婇悙顏勨偓鎴﹀磿椤栫偛鍨傜憸鐗堝笒閻撴﹢鏌熸潏楣冩闁哄拋鍓熼弻娑㈠即閵娿儱顫┑顕嗙到閻楁捇骞冨Δ鍐╁枂闁告洦鍓涢ˇ顓㈡⒑閸濄儱校闁绘濞€婵″瓨鎷呯化鏇燁潔濠殿喗顨呭Λ娆撳磽闂堟侗娓婚柕鍫濇閸у﹪鏌涚€ｎ偅宕岄柡灞稿墲閹峰懘妫冨☉鎺戜壕婵犻潧妫鏍磽娴ｈ鐒介柣鐔风秺閺屽秷顧侀柛鎾寸懇閳ワ箓宕堕宥嗏枆闂備線娼荤徊鐣岀礊婵犲偆娼栨繛宸簻瀹告繂鈹戦悩鎻掝伀闁绘帟鍋愮槐鎾存媴閹绘帊澹曞┑鐐存尰閸╁啴宕戦幘鎼闁绘劖褰冮弳锝嗩殽閻愬樊鍎忛柍瑙勫灴瀹曟﹢鍩￠崒娑欑帆闂傚倸鍊烽懗鍓佸垝椤栫偞鏅梻浣筋嚙缁绘垵鐣濈粙娆惧殨闁规儼妫勯悡娑㈡煕濞戝崬鏋ら柛姗€浜堕弻锝嗘償椤栨粎校闂佸憡鎸婚悷鈺侇嚕缁嬪簱妲堟慨姗堢到娴滈箖鎮峰▎蹇擃仾缁剧偓鎮傞弻娑㈠Ω閵夛絽浠柦妯荤箞閺岀喓绱掗姀鐘崇亶闂佺粯鎸搁崯浼村箟缁嬫鐓ラ柛顐ｇ箘椤︻厼鈹戦绛嬬劸濞存粠鍓熼幆灞解枎閹惧鍘卞銈嗗姉婵挳宕濆鑸电厽闁靛牆娲ゆ禍鍓х磼缂佹绠炴俊顐㈠暙閳藉宕￠悙鎻掝棈缂傚倸鍊烽懗鑸垫叏閻㈠憡鍋傞柨鐔哄Т閽冪喖鏌￠崶椋庣？闁汇倐鍋撻梻浣告惈濞层劑宕愰鈶╂婵炲棗娴风粻姘舵⒑閸︻厾甯涢悽顖滃仦閺呭爼鏁冮崒娑氬幐闁诲繒鍋熼崑鎾剁矆婢跺瞼纾奸柣妯虹－濞插鈧鍠楅幐鎶藉箖濞嗘挸绠涢柍杞扮婵酣鏌х紒妯煎⒌闁哄矉绲借灒闁告繂瀚鍥⒑閸濄儱校閽冮亶鏌熸笟鍨缂佺粯绻堝畷銊╊敋閸涱剙鎽嬮梻鍌欒兌閹虫挸顕ｉ崼鏇炵闁告劘灏欓弳锕傛煟閺冨倵鎷￠柡浣告閺屽秷顧侀柛鎾跺枎閻ｅ嘲顭ㄩ崱鎰睏闂佸湱鍎ら幐鎾箯濞差亝鈷戦柛娑橈功閳藉鏌嶉娑欑妞ゃ垺妫冨畷鐓庮熆椤庢澘鎳愮壕濂告倵閿濆骸骞楃痪顓炵埣閺岋繝宕遍銏☆€嶇紓浣虹帛缁诲啰鎹㈠┑瀣＜婵犲﹤鍠氶弶鎼佹⒒娴ｈ櫣甯涢悽顖滃枛瀹曟垿骞囬弶璺ㄥ姦濡炪倖宸婚崑鎾剁磼閻樿尙效鐎规洘娲熷畷锟犳倷瀹ュ棛鈽夐柣锝嗙箞瀹曠喖顢曢妶搴℃暩?
              </DropdownMenuItem>
              <DropdownMenuItem v-if="role === 'admin' || role === 'operator'" class="cursor-pointer" @click="router.push('/audit')">
                <FileSearch class="mr-2 size-4" />
                闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤濠€閬嶅焵椤掑倹鍤€閻庢凹鍙冨畷宕囧鐎ｃ劋姹楅梺鍦劋閸ㄥ綊宕愰悙宸富闁靛牆妫楃粭鎺撱亜閿斿灝宓嗙€殿喗鐓￠、鏃堝醇閻旇渹鐢绘繝鐢靛Т閿曘倝宕幘顔肩煑闁告洦鍨遍悡蹇涙煕閳╁喚娈旈柡鍡到閳规垿鏁嶉崟顐㈠箣闂佺硶鏂侀崜婵嬪箯閸涱喚鐟规い鏍ㄧ濞呭秴鈹戦悩鍨毄闁稿鍋ら獮鎰節濮橆厼娈為梺璇″灱閻忔劕煤椤忓懏娅囬梺绋挎湰濮樸劑寮昏濮婃椽妫冨☉姘鳖唺婵犳鍣崣鍐嚕閵婏妇顩烽悗锝庡亞閸樿棄鈹戦埥鍡楃仴闁稿鍔楅弫顔尖槈濞嗘垹顔曢梺鐟板暱閸㈣尙鈧哎鍔嶇粋宥咁煥閸喓鍘甸柣搴㈢⊕椤洨绮婚弽顓熺厱闁挎繂鐗滃鎰磼缂佹娲存鐐存崌楠炴帡骞橀崗鍛▕濠电姵顔栭崰鏍晝閵娿儮鏋嶉柨婵嗘噳濡插牓鏌ｉ姀銏╃劸鐎瑰憡绻冮妵鍕箻鐎靛摜鐣洪梺娲诲亜缁绘ê顫忓ú顏呭殥闁靛牆鎳嶅▽顏嗙磽娴ｅ壊鍎忕紒缁樏悾鐑藉即閵忊槅妫冨┑鐐村灦绾板秴鈻撻幆褉鏀介柣妯款嚋瀹搞儵鏌涢悢鍝勨枅鐎殿喓鍔嶇粋鎺斺偓锝庡亜閳ь剛鏁婚弻銊モ攽閸℃瑥鍤紓浣靛妺缁瑩寮婚妸銉㈡婵炲棙鍨堕崳浼存⒑閸濆嫮鐏遍柛鐘崇墪閻ｅ嘲螖閸涱喖娈愰梺鍐叉惈閸婂綊顢欓崘顔解拻濞达絽鎲￠崯鐐烘煛鐏炶濡跨紒顔芥閵囨劙骞掗幋鐐葱氭繝鐢靛仦閸垶宕归崷顓犱笉闁规儼濮ら悡娆撴煟閹邦垱顥夊┑陇鍋愮槐鎾愁吋閸滃啳鍚悗娈垮櫘閸嬪﹪鐛崶顒€绾ч柛顭戝枤閻涒晜淇婇悙顏勨偓鏍蓟閵娾晛瑙﹂悗锝庝簴閺嬫梹鎱ㄥ璇蹭壕濠殿喖锕︾划顖炲箯閸涱垳椹抽悗锝庝簼閻ｄ即姊绘担瑙勫仩闁告柨顑夊畷锟犲箮閽樺鐣洪悷婊勬閻涱喖螣閸忕厧鐝伴梺鑹板閸╂牠骞夐悧鍫㈢瘈闁汇垽娼ф禒锕傛煕椤垵鐏︾€规洜鎳撶叅妞ゅ繐瀚敍娑㈡⒑閸涘﹥澶勯柛銊╀憾閹€斥槈濮楀棛鍞甸柣鐘烘〃鐠€锕傚磿韫囨稒鐓熼煫鍥ь儏閸旀粓鏌曢崶褍顏い銏℃礋婵偓闁炽儴娅曢悘搴ㄦ⒒娴ｇ瓔鍤冮柛鐘愁殜閵嗗啴宕奸妷銉х枀闂佸湱铏庨崰鏍矆鐎ｎ偁浜滈柟鐑樺灥娴滅偞淇婇懠顒€顣肩紒缁樼箞閹粙妫冨☉妤冩崟闁诲孩顔栭崰鏍偉婵傜鏋侀悗锝庝憾濞撳鏌曢崼婵嬵€楁鐐寸墬缁绘稑霉鐎ｎ偅鐝栫紓渚囧枦椤曆囧煡婢跺á鐔兼煥鐎ｅ灚缍屽┑鐘殿暯濡插懘宕归幎钘夊偍鐟滄棃鎮伴鈧獮鍥偋閸碍瀚藉┑鐐舵彧缁茶偐鎷冮敃鍌涘€垮Δ锝呭暞閻撴盯鏌涢顐簻濠⒀勬尦閺岀喖鎼归銈囩杽閻庤娲樼划蹇浰囩捄琛℃斀?
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem class="cursor-pointer text-destructive focus:text-destructive" @click="handleLogout">
                <LogOut class="mr-2 size-4" />
                闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁诡垎鍐ｆ寖闂佺娅曢幑鍥灳閺冨牆绀冩い蹇庣娴滈箖鏌ㄥ┑鍡欏嚬缂併劎绮妵鍕箳鐎ｎ亞浠鹃梺闈涙搐鐎氫即鐛崶顒夋晜闁糕剝鐟ч崢顖炴⒒娴ｅ憡鎯堥悶姘煎亰瀹曟繈骞嬮敃鈧粻鏍煏韫囧鈧洘瀵奸悩缁樼厱闁哄洨鍠庨悘鐔兼煕閵娿儺鐓奸柟顖楀亾濡炪倕绻愰悧鍡欑不濮樿鲸鍠愭繝濠傜墛閸嬪倸鈹戦崒姘暈闁绘挻鐩幃姗€鎮欓崹顐ｇ彧闁哥喓顭堥—鍐Φ閸楃偛鈧崵绮ｉ弮鍫熺厸閻忕偛澧藉ú瀛橆殽閻愭惌鐒介柟鐟板閹粌螣闂傛挳鍋楅梻浣筋嚙鐎涒晠顢欓弽顓炵獥婵炴垯鍩勯弫瀣喐閺冨牆鏄ラ柕澶涚畱缁剁偛鈹戦悩鎻掝劉闁稿秶鏁诲娲箰鎼达絿鐣甸梺鐟板暱缁夌數绮╅悢鐓庡嵆闁靛繆妾ч幏娲⒑閸︻収鐒炬繛鎾棑缁骞樺鍕閹晠宕ｆ径濠冩畼缂傚倷绀侀崐鍝ョ矓閹绢喖鐓橀柟杈剧畱闁卞洦鎱ㄥ鍡楀幐濠㈣娲熼弻锝夋偄閸濄儲鍣ч柣搴㈠嚬閸樺墽鍒掗崼銉ョ劦妞ゆ帒瀚埛鎴炵箾閼奸鍤欐鐐寸墵閺屾稒绻濋崒婊€铏庡銈嗘穿缁插墽鎹㈠┑鍡╂僵妞ゆ挾鍠愰悵顐︽⒒娴ｅ憡鍟炴繛璇ч檮缁傚秴鈹戠€ｎ亞顦伴梺鍛婂姦閸犳鍩涢幋锔界厱婵炴垶锕弨濠氭倵閸偆鎳囬柡灞剧洴瀵挳濡搁妷銈囩泿闂備浇顕х换鍡涘焵椤掍焦鐏遍柡鈧禒瀣闁规儼妫勭壕瑙勪繆閵堝嫮鍔嶉柛娆忕箻閺岋綁骞嬮敐鍡╂缂佹儳澧界划顖滄崲濞戙垹绠ｆ繛鍡楃箳閸旀挳姊烘潪鎵槮閻庢凹鍓熼垾锕傚锤濡や礁娈濋梻鍌氱墛缁嬫垿锝炲畝鍕拺闁告繂瀚烽崕搴ｇ磼閼搁潧鍝虹€殿喖顭烽幃銏ゅ礂閻撳簼缃曢梻浣稿閸嬪棝宕伴幘璇茬闁炽儲绶為弮鍫熷亹闂傚牊绋愰弶顓㈡⒑閹肩偛濡虹紒顔界懃椤曪絿鎷犲顔兼倯闂佹悶鍎崝灞剧閹烘鈷戦柣鎰閸旀岸鏌涘Ο鑽ゅ缂佹梻鍠栧鎾閳锯偓閹风粯绻涙潏鍓у埌闁硅绻濆畷顖炴倷閻㈢數锛滈柣鐘叉处瑜板啴寮抽敐澶嬬厪闁糕剝顨呴弳锝団偓瑙勬礀瀹曨剟鍩㈡惔銊ョ疀妞ゆ巻鍋撶紒銊ｅ劜缁绘繈鎮介棃娑掓瀰濠电偘鍖犻崶鑸垫櫈闂佺硶鍓濈粙鎴犲婵犳碍鐓忓┑鐐靛亾濞呭棝鏌嶉柨瀣诞闁哄本鐩、鏇㈠Χ閸涱喚浜栭梻浣哥－椤戞洟宕曞畷鍥潟闁圭儤顨忛弫濠囨煠濞村娅呴柣鎾跺枎閳规垿顢欑涵閿嬫暰濠碉紕鍋樼划娆撶嵁閸愵喗鍊婚柦妯侯槺妤犲洭姊洪崷顓х劸閻庢稈鏅犻幆渚€鏁愭径瀣ф嫽婵炶揪缍€椤濡甸悢鍏肩厱婵☆垱浜介崑銏⑩偓瑙勬礃閸旀瑩鐛弽銊﹀闁荤喖顣﹂幃锝夋⒒娴ｈ櫣甯涢柛銊у帶铻為柛鏇ㄥ灠绾偓闂佽鍎兼慨銈夋偂韫囨稓鍙撻柛銉ｅ妽缁€鈧柛鐔侯焾椤啴濡堕崱妯锋嫻闁汇埄鍨辩敮锟犲灳閺冨牆绀冩い鏂挎瑜旈弻娑㈠焺閸愬墽鍔烽梺鍛婄懃濡鍩?
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div class="border-t border-border px-4 py-2 md:hidden">
        <Tabs :model-value="activeMode" @update:model-value="onModeChange">
          <TabsList class="grid w-full grid-cols-2 bg-muted/50 p-1 rounded-lg gap-1">
            <TabsTrigger 
              value="defense" 
              class="cursor-pointer rounded-md transition-[transform,opacity] duration-220 hover:-translate-y-px 
              data-[state=active]:!bg-[#3B82F6] data-[state=active]:!text-white data-[state=active]:shadow-sm
              hover:text-[#3B82F6] data-[state=active]:hover:text-white"
            >
              闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁绘劦鍓欓崝銈囩磽瀹ュ拑韬€殿喖顭烽幃銏ゅ礂鐏忔牗瀚介梺璇查叄濞佳勭珶婵犲伣锝夘敊閸撗咃紲闂佺粯鍔﹂崜娆撳礉閵堝洨纾界€广儱鎷戦煬顒傗偓娈垮枛椤兘骞冮姀銈呯閻忓繑鐗楃€氫粙姊虹拠鏌ュ弰婵炰匠鍕彾濠电姴浼ｉ敐澶樻晪闁逞屽墮椤繘宕崟鎳峰洤鐐婄憸澶愬磻閹捐围濠㈣泛锕﹂悰銉モ攽鎺抽崐鏇㈠箠鎼淬埄鏀伴梻鍌欑閹测€趁洪敃鍌氬瀭濞村吋娼欑粈鍐煃瑜滈崜鐔奉潖濞差亝顥堟繛娣€栭惄顖氱暦閵娾晩鏁嶆繝濠傛噹閻愬﹥绻濋悽闈浶ラ柡浣规倐瀹曟垵鈽夐姀鈥充槐闂侀潧臎閸愩劎浜伴柣搴″帨閸嬫捇鏌嶈閸撴稑危閹扮増鍊烽悗闈涙憸閻﹀牓姊洪幖鐐插妧闁糕剝蓱閸熷搫鈹戦悩鍨毄闁稿鍋ゅ畷褰掝敍閻愭彃鐎梺闈╁瘜閸樼偓绋夊鍡欑闁瑰瓨鐟ラ悘顏堟煟閹惧瓨绀嬮柣鎿冨亰瀹曞爼濡搁敃鈧棄宥夋⒑閻熸澘绾ч柟顔煎€垮濠氬Χ婢跺鍎銈嗗姧缁茬粯绂掗姀鐘斀妞ゆ梻銆嬫Λ姘箾閸滃啰鎮兼俊鍙夊姍楠炴帡骞婂畷鍥ф灈闁圭厧缍婂畷鐑筋敇閻旈攱鐝梻鍌氬€搁崐鐑芥倿閿旈敮鍋撶粭娑樺幘妤﹁法鐤€婵炴垶顭囬敍娆忊攽閻樼粯娑ф俊顐ｆ尦閹虫捇宕归琛″亾閹烘埈娼╅柨婵嗘噸婢规洘绻濆▓鍨灈闁挎洏鍔岄埢宥夋晲閸ヮ煈娼熼梺鍦劋閸わ箓鎮㈤懡銈囨澑闂佹寧绻傜€氼噣鎯勬惔銊︾叄濞村吋鐟ч崚浼存煃鐟欏嫬鐏撮柟顔规櫊瀹曪絾寰勭€ｎ偄鈧绱撴担鍝勪壕闁稿骸鍟块…鍥晸閻樺啿浜楀銈嗗姧缁犳垿鎮欐繝鍥ㄧ厪濠电倯鈧崑鎾斥攽椤斿吋鍠樻慨濠冩そ楠炲酣鎳為妷锔芥闂備焦鎮堕崝灞筋焽閿熺姷宓侀柛鎰靛枟閻撱儵鎮楅敐搴′簻妞ゅ孩鎹囧濠氬磼濮樺崬顤€缂備礁顑呴悧鎾崇暦閹达箑绠婚悹鍥ㄥ絻瀹撳棝姊洪棃娑氱濠殿喚鍏樺畷婵嬫晝閳ь剟鈥旈崘顔嘉ч柛鈩冾殘閻熸劙姊洪悡搴ｆ瀮闁糕晜鐗犲鏌ュ醇閺囩偛鐎銈嗗姦閸嬪懘顢欓弮鍫熲拺缂備焦锚婵矂鎮樿箛鏃傛噭闁哄懎鐖奸弫鍐焵椤掑嫬鐓橀柟杈剧畱閻掓椽鏌涢幇銊︽珔闁逞屽墯閸旀洟鍩為幋锔芥櫖闁告洦鍋勯獮瀣渻閵堝啫鐏柣鐔叉櫊楠炴劖绻濋崘銊х獮閻庡厜鍋撻柍褜鍓氬鍕礋椤栨稈鎷婚梺绋挎湰閼归箖鍩€椤掑倸鍘撮柟铏殜瀹曟粍鎷呴悷鏉垮箲闂備礁澹婇崑鍛洪弽顐ょ焼闁割偆鍠撶弧鈧梻鍌氱墛娓氭宕曞澶嬬厓鐟滄粓宕滃▎鎾崇柈闁哄鍨归弳锕傛煏婵犲繘妾紓宥呮喘閺屾盯骞樺Δ鈧幊澶娢涢妸銉㈡斀闁挎稑瀚禍濂告煕婵犲啰澧电€规洘绻嗛ˇ瑙勬叏婵犱胶鐭欑€规洜鍠栭、娑橆潩閸楃偛绠?
            </TabsTrigger>
            <TabsTrigger 
              value="probe" 
              class="cursor-pointer rounded-md transition-[transform,opacity] duration-220 hover:-translate-y-px 
              data-[state=active]:!bg-[#F97316] data-[state=active]:!text-white data-[state=active]:shadow-sm
              hover:text-[#F97316] data-[state=active]:hover:text-white"
            >
              婵犵數濮烽弫鍛婃叏閻戣棄鏋侀柛娑橈攻閸欏繘鏌ｉ幋锝嗩棄闁哄绶氶弻娑樷槈濮楀牊鏁鹃梺鍛婄懃缁绘﹢寮婚敐澶婄闁挎繂妫Λ鍕⒑閸濆嫷鍎庣紒鑸靛哺瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁绘劦鍓欓崝銈嗐亜椤撶姴鍘寸€殿喖顭烽弫鎰緞婵犲嫮鏉告俊鐐€栫敮濠囨倿閿曞倸纾块柟鍓х帛閳锋垿鏌熼懖鈺佷粶濠碘€炽偢閺屾稒绻濋崒娑樹淮閻庢鍠涢褔鍩ユ径鎰潊闁冲搫鍊瑰▍鍥⒒娴ｇ懓顕滅紒璇插€歌灋婵炴垟鎳為崶顒€唯鐟滃繒澹曢挊澹濆綊鏁愰崨顔藉創闁哄稄绻濋幃宄邦煥閸曨剛鍑￠梺鍝ュ枎閻°劍绌辨繝鍥х妞ゆ棁鍋愰濠囨⒑鐟欏嫭鍎楅柛妯圭矙瀹曟捇鎮介崨濞炬嫼闂佸湱顭堝ù椋庣不閹剧粯鐓欓柛鎰皺鏍＄紓浣规⒒閸犳牕顕ｉ幘顔藉亜闁告挷鑳堕悾楣冩⒒娴ｈ櫣甯涢柛鏃撻檮缁傚秴顭ㄩ崼婵堝姦濡炪倖甯婄粈渚€鎮樼€电硶鍋撶憴鍕缂傚秴锕獮鍐煥閸忓墽鍠撴禍鎼佸冀閵婏附娈兼繝鐢靛Х閺佹悂宕戝☉妯滅喐绻濋崶褏鍔﹀銈嗗笒椤︻喚鑺辩紒妯肩鐎瑰壊鍠栧顕€鏌ｅ☉鍗炴灍闁诡垱妫冩俊鎼佹晝閳ь剙鈻撻悢鍏尖拺闂傚牊鍐荤槐锟犳煕閹扳晛濡挎い鎾跺帶閳规垿鎮╅崹顐ｆ瘎闂佺顑囬崑銈夌嵁閹邦厾绡€婵﹩鍘煎▓鐐翠繆閵堝繒鍒伴柛鐕佸灦瀹曟劙鎳滈悽鐢电槇闂傚倸鐗婄粙鎺撳緞閸曨垱鐓曟繛鍡楃箳缁犲鏌＄仦鍓р槈闁伙絾绻堥崺鈧い鎺戝绾惧鏌ｉ幇顔煎妺闁稿鍊块弻锟犲炊閵夈儳浠鹃梺缁樻尭閸熸挳寮诲☉妯锋斀闁糕剝顨忔导宀勬⒑缁嬪灝顒㈤柛銊ユ贡濡叉劙骞掑Δ鈧悡銏ゆ煃瑜滈崜鐔风暦閹达箑绠荤紓浣诡焽閸樹粙鏌熼崗鑲╂殬闁稿鍊曢…鍥箛椤撶姷顔曢梺鍦帛鐢偟绮婚懡銈傚亾鐟欏嫭绀冪紒璇茬墦閻涱喚鈧綆鍠楅弲婊堟偠濞戞巻鍋撻崗鍛棜濠电偠鎻徊鑺ョ珶婵犲偆鐒介柕濞炬櫆閻撳啰鎲稿鍫濈闁绘棁鍋愬畵渚€鏌涢幇闈涙珮闁轰礁鍊块弻娑㈩敃閿濆洨鐣奸梺鍛婃缁犳垿鈥旈崘顔嘉ч柛鈩冾殘閻熴劑鏌ｆ惔銏犲毈闁告挾鍠栭獮濠傤煥閸涱喖鏋傞梺鍛婃处閸橀箖顢欓弴銏″€甸柣鐔告緲椤ュ繘鏌涢悩铏闁奸缚椴哥缓浠嬪川婵犲嫬甯楅梻鍌欑閻忔繈顢栭崨顖滅當闁圭儤顨嗛悡蹇涙煕閳╁厾顏嗙箔閹烘挶浜滄い鎰剁悼缁犵偤鏌℃担鐟板鐎规洏鍔戦、妤呭焵椤掑媻澶婎潩椤戣姤鏂€闂佺粯锚閻忔岸寮抽埡鍛厱閻庯綆鍋撻懓璺ㄢ偓瑙勬礈婵炩偓闁诡喒鏅濋幏鐘绘嚑椤掑效闂傚倷绀佹竟濠囨偂閸儱纾婚柟鐑橆殔閻ゎ喚鈧箍鍎遍ˇ浼村煕閹烘垟鏀介柣妯荤叀椤庢霉濠婂嫮鐭嬬紒缁樼〒閹风姾顦撮柣锝変憾閹繝濡堕崱妯哄伎濠碉紕鍋犻褎绂嶆ィ鍐┾拺闁圭娴风粻姗€鏌涚€ｃ劌鈧洟顢氶敐澶婄妞ゆ梻鈷堝濠囨⒑閹稿海鈽夐悗姘煎墴閻涱噣骞囬悧鍫氭嫽婵炶揪缍€椤宕戦悩缁樼厱閹兼惌鍠栭悘锔锯偓瑙勬礃濞茬喖寮婚崱妤婂悑闁糕剝銇涢崑鎾诲醇閺囩喓鍘撻梺鍛婄箓鐎氼參宕宠ぐ鎺撶厽?
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </header>

    <div class="relative flex min-h-0 flex-1 overflow-hidden">
      <div ref="maskWrapRef" class="pointer-events-none fixed inset-0 z-[100] hidden flex w-full h-full">
        <div ref="impactPulseRef" class="absolute top-1/2 left-1/2 size-20 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary opacity-0" />
        <div
          v-for="panelIndex in maskPanels"
          :key="`mask-panel-${panelIndex}`"
          :ref="setMaskPanelRef"
          class="h-full flex-1 bg-background/50 border-r border-border/50 last:border-r-0 origin-top"
        />
        <div ref="inkTopRef" class="absolute top-[30%] left-0 h-0.5 w-full bg-primary shadow-[0_0_15px_var(--primary)] opacity-0" />
        <div ref="inkBottomRef" class="absolute bottom-[30%] left-0 h-0.5 w-full bg-primary shadow-[0_0_15px_var(--primary)] opacity-0" />
        <div 
          ref="transitionTitleRef" 
          class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-6xl md:text-8xl font-black tracking-[0.5em] text-transparent bg-clip-text bg-gradient-to-b from-white via-white to-white/10 opacity-0 whitespace-nowrap z-50 select-none pointer-events-none"
          style="text-shadow: 0 0 40px var(--primary);"
        >
          {{ transitionTitleText }}
        </div>
      </div>

      <aside
        ref="sidebarRef"
        class="relative hidden shrink-0 border-r border-sidebar-border bg-sidebar transition-[transform,opacity] duration-260 ease-[cubic-bezier(0.4,0,0.2,1)] md:flex md:flex-col"
        :class="sidebarCollapsed ? 'px-2 py-3' : 'p-3'"
        :style="{ width: `${sidebarCurrentWidth}px` }"
      >
        <div
          class="mb-3 min-h-8 rounded-md border transition-[transform,opacity] duration-260 ease-[cubic-bezier(0.4,0,0.2,1)] backdrop-blur-sm bg-background/60 flex items-center justify-center overflow-hidden"
          :class="[
            sidebarCollapsed ? 'px-2 py-2 text-center' : 'px-3 py-2',
            activeMode === 'defense' 
              ? 'border-blue-500 text-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.1)]' 
              : 'border-orange-500 text-orange-500 shadow-[0_0_15px_rgba(249,115,22,0.1)]'
          ]"
        >
          <p class="font-medium tracking-wide leading-none flex items-center justify-center" :class="sidebarCollapsed ? 'text-[11px]' : 'text-xs'">
            <span
              class="sidebar-mode-label"
              :class="sidebarCollapsed ? 'sidebar-mode-label-collapsed' : 'sidebar-mode-label-expanded'"
            >
              {{ sidebarCollapsed ? (activeMode === 'defense' ? 'Defense' : 'Probe') : activeModeLabel }}
            </span>
          </p>
        </div>

        <nav class="flex-1 space-y-1 overflow-hidden">
          <router-link
            v-for="item in currentSidebarItems"
            :key="item.to"
            :to="item.to"
            data-sidebar-item="true"
            :title="sidebarCollapsed ? item.label : undefined"
            class="flex items-center rounded-md py-2 text-sm text-sidebar-foreground transition-[transform,opacity] duration-220 hover:-translate-y-px hover:bg-sidebar-accent hover:opacity-95 cursor-pointer"
            :class="sidebarCollapsed ? 'justify-center px-2' : 'gap-2 px-3'"
            active-class="bg-sidebar-accent text-sidebar-accent-foreground"
          >
            <component :is="item.icon" class="size-4" />
            <span
              class="sidebar-item-label"
              :class="sidebarCollapsed ? 'sidebar-item-label-collapsed' : 'sidebar-item-label-expanded'"
            >
              {{ item.label }}
            </span>
          </router-link>
        </nav>

        <div class="mt-2 border-t border-sidebar-border/70 pt-2">
          <button
            type="button"
            class="flex h-11 w-full items-center rounded-md text-sidebar-foreground transition-[transform,opacity] duration-220 hover:-translate-y-px hover:bg-sidebar-accent hover:opacity-95 focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
            :class="sidebarCollapsed ? 'justify-center px-2' : 'gap-2 px-3'"
            :title="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
            :aria-label="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
            @click="toggleSidebarCollapsed"
          >
            <ChevronRight
              class="size-4 transition-transform duration-220 ease-out"
              :class="sidebarCollapsed ? 'rotate-0' : 'rotate-180'"
            />
            <span
              class="sidebar-item-label text-sm"
              :class="sidebarCollapsed ? 'sidebar-item-label-collapsed' : 'sidebar-item-label-expanded'"
            >
              闂備浇銆€閸嬫捇鏌熼婊冾暭鐎规洖鍟块妴鎺戭潩閳ь剟宕卞▎鎴濋獎闂?
            </span>
          </button>
        </div>

        <div
          class="absolute top-0 -right-1 z-20 h-full w-2 cursor-col-resize"
          role="separator"
          aria-orientation="vertical"
          @mousedown="startSidebarResize"
        >
          <div
            class="mx-auto h-full w-px bg-transparent transition-opacity duration-180 hover:opacity-80 hover:bg-border"
            :class="isSidebarResizing ? 'bg-primary/60' : ''"
          />
        </div>
      </aside>

      <main
        ref="contentRef"
        class="min-w-0 flex-1 overflow-y-auto bg-background/50"
      >
        <div
          class="relative h-full transition-[opacity,transform] duration-260 ease-out"
          :class="isRouteChanging ? 'content-loading' : 'content-ready'"
        >
          <div
            v-if="isRouteChanging"
            class="pointer-events-none absolute inset-0 z-20 route-content-overlay"
            :style="{ opacity: String(Math.min(0.16, Math.max(0.06, 1 - routeProgress))) }"
          />
          <router-view v-slot="{ Component, route: childRoute }">
            <Transition name="fade-slide" mode="out-in" appear>
              <div :key="childRoute.fullPath" class="route-page h-full">
                <component :is="Component" />
              </div>
            </Transition>
          </router-view>
        </div>
      </main>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUpdate, onMounted, onUnmounted, ref, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useActiveMode } from '@/composables/useActiveMode'
import { hasAnyPermission, parseStoredUserInfo } from '@/composables/useAuthz'
import { authApi } from '../api/auth'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import gsap from 'gsap'
import {
  Activity,
  Bell,
  Blocks,
  BrainCircuit,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight,
  FileSearch,
  LogOut,
  Moon,
  PanelLeft,
  Radar,
  ScanSearch,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sun,
  UserRound,
} from 'lucide-vue-next'

type ModeKey = 'defense' | 'probe'

const router = useRouter()
const route = useRoute()
const { activeMode, lastActiveMode } = useActiveMode()

const username = ref('user')
const role = ref('viewer')
const notifications = ref([
  { id: 'n-1', title: 'Workspace status', content: 'Page transitions do not interrupt backend tasks.', time: 'Just now', read: false },
  { id: 'n-2', title: 'Audit export done', content: 'Latest audit export task finished.', time: '5 min ago', read: false },
  { id: 'n-3', title: 'Scan reminder', content: 'There are scan results waiting for confirmation.', time: '15 min ago', read: true },
])
const NOTIF_PAGE_SIZE = 5
const notifPage = ref(1)
const notifTotalPages = computed(() => Math.max(1, Math.ceil(notifications.value.length / NOTIF_PAGE_SIZE)))
const pagedNotifications = computed(() => {
  const start = (notifPage.value - 1) * NOTIF_PAGE_SIZE
  return notifications.value.slice(start, start + NOTIF_PAGE_SIZE)
})
const shellRef = ref<HTMLElement | null>(null)
const sidebarRef = ref<HTMLElement | null>(null)

// 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤濠€閬嶅焵椤掑倹鍤€閻庢凹鍙冨畷宕囧鐎ｃ劋姹楅梺鍦劋閸ㄥ綊宕愰悙鐑樺仭婵犲﹤鍟扮粻鑽も偓娈垮枟婵炲﹪寮崘顔肩＜婵炴垶鑹鹃獮鍫熶繆閻愵亜鈧倝宕㈡禒瀣瀭闁割煈鍋嗛々鍙夌節闂堟侗鍎愰柣鎾存礃缁绘盯宕卞Δ鍐唺缂備胶濮垫繛濠囧蓟瀹ュ牜妾ㄩ梺鍛婃尰缁诲牓鏁愰悙鏉戠窞濠电偞甯楀钘夘嚕娴犲鈧牠鍩勯崘鈹夸虎闂佽桨绀侀崐鍧楀箰婵犲啫绶炲┑鐘插缁ㄥ瓨绻濋悽闈涗粶妞ゆ洦鍙冨畷銏ｎ樄闁诡喗妞芥俊鎼佸煛閸屾矮绨甸梻渚€娼чˇ顐﹀疾濠婂牊鍋傛繛鎴欏灪閻撴洟鏌曟径鍫濈仾婵炲懎鎳庨湁闁绘ê纾惌鎺楁煛鐏炵晫啸妞ぱ傜窔閺屾盯骞橀弶鎴濇懙濡ょ姷鍋涢崯鏉戠暦閹烘埈娼╅弶鍫涘妽椤旀洟鏌ｉ悢鍝ョ煂濠⒀勵殘閺侇噣骞掗弬娆炬婵犻潧鍊搁幉锟犳偂閻斿吋鐓欓梺顓ㄧ畱婢у鏌涢妶鍥ф灈闁哄本绋戣灒闁稿繐鍚嬪В鍫濃攽椤旂》榫氭繛鍜冪秮楠炲繘鎮╃拠鑼紜閻庤娲栧ú锝夊礌閺嵮€鏀介柣姗嗗亝婵即鏌涢弴鐐典粵闁汇倓绶氶弻锕€螣閻撳孩鐎诲銈庡幖濞硷繝骞婂鍫燁棃婵炴垶锕╁鏃堟⒒娴ｈ櫣甯涢柟绋款煼閹嫰顢涢悙鑼暫濠德板€曢幊蹇涘疾閺屻儲鐓曢悘鐐插⒔閳洟鏌ｅ┑鍥╁⒈缂佽鲸鎸婚幏鍛存偡閺夋娼旀繝娈垮枛閿曘倝鈥﹂悜钘夋槬闁逞屽墯閵囧嫰骞掑鍥獥闂佸摜鍠庣换姗€寮诲☉銏″亹鐎规洖娲ら埛宀勬⒑鐠団€虫灁闁稿海鏁婚獮鍐焺閸愨晛鍔呴梺鎸庣箓濡瑩顢欓弴銏♀拻濞达綀娅ｇ敮娑㈡煙缁嬫寧鎲搁柤楦夸含閹瑰嫭鎷呴弴顏嗙М鐎规洖銈搁幃銏ゅ礈娴ｈ櫣鏆板┑锛勫亼閸婃牠鎮уΔ鍛仭闁靛ň鏅╅弫鍡涙煟閺傚灝鎮戦柣鎾跺枛楠炴牕菐椤掆偓閻忣亞绱撳鍡楃伌闁哄苯绉堕幉鎾礋椤愩倓绱濋梻浣筋嚃閸犳鎮烽埡鍛疇闁绘ɑ妞块弫鍡椕归敐鍥ㄥ殌闁哄鐩濠氬磼濞嗘垵濡介梺璇″枛閻栫厧鐣烽幇鏉垮嵆闁靛骏绱曢崢鎰版⒑閹稿海绠撻柟铏姍瀵娊鏁冮崒娑氬幍闂佺粯顨呴悧濠勬閺屻儲鐓曢柟鑸妼娴滄儳鈹戦敍鍕杭闁稿﹥鐗犲畷婵婎槾鐎垫澘锕幊鐐哄Ψ閿曗偓閸斿懏绻濋悽闈浶㈤柛濠勬暬瀵劍绂掔€ｎ偆鍘介梺褰掑亰閸樼晫绱為幋锔界厽闊洦娲栭弸娑㈡煛鐏炲墽娲村┑鈩冩倐婵＄兘鏁冩担渚敤缂傚倸鍊风欢锟犲窗閺嶎厸鈧箓鎮滈挊澶嬬€梺褰掑亰閸樿偐娆㈤悙鐑樺€甸柨婵嗛婢ь喗顨ラ悙鎼疁婵﹦绮换婵囨償閳ヨ尙鐩庢繝鐢靛仩椤曟粎绮婚幋锔肩稏闊洦鍝庢禍褰掓煙閻戞ê娈鹃柨鏇炲€归悡鐔兼煛閸愩劍绁╅柛鐔风箻閺岋綁鎮㈤悡搴濆枈闂佺粯鎸堕崕鐢哥嵁閺嶎偀鍋撳☉娆樼劷缂佺姷鍋ら弻娑氣偓锝庡亽濞堟粍鎱ㄦ繝鍐┿仢婵☆偄鍟埥澶娾枎濡椿妫ょ紓鍌氬€风拋鏌ュ磻閹剧偨鈧帒顫濋敐鍛闂備胶纭堕弬鍌炲垂濞差亜绠氶柡鍐ㄧ墕鎯熼梺闈涳紡閸涱喗绶繝纰夌磿閸嬫垿宕愰弽顓炶摕闁靛闄勫▍鐘绘煢濡尨绱氶柨婵嗩槸閻愬﹥銇勯幒宥堫唹闁归绮换娑欐綇閸撗呅氬銈庡亜椤﹂潧鐣烽幋锔藉亹缂備焦顭囬崢閬嶆煙閸忓吋鍎楅柛鐘崇墵閹﹢鏁傞柨顖氫壕閻熸瑥瀚粈鍐磼鐠囨彃鏆ｆ鐐叉瀵噣宕煎顏佹櫊閺屾洘寰勯崼婵嗗婵炲瓨绮岄悥鐓庮潖缂佹ɑ濯撮柛娑橈工閺嗗牏绱撴担鍓插剱闁搞劌娼″顐﹀礃椤旇姤娅嗛梺璇″瀻閸愬啯宀稿娲焻閻愯尪瀚板褍鐡ㄩ幈銊︾節閸愨斂浠㈠┑鈽嗗亜閸燁偊鍩ユ径鎰潊闁靛繒濮甸妵婵堢磽閸屾艾鈧嘲霉閸パ屽殨闁规崘娉涢崹婵囩箾閸℃ɑ灏紒鐘崇墵閺屻劑鎮㈤崫鍕戙垻绱掗悩宕団姇闁靛洤瀚板顒勫垂椤旇瀵栭梻浣瑰缁嬫帞鍒掗幘璇茶摕闁挎繂妫欓崕鐔搞亜閺嶃劎鐭岄弽锟犳⒒娴ｄ警鐒炬い鎴濇嚇楠炲﹪骞囬鐙€娲搁梺褰掓？閻掞箓藟閸喓绠鹃柟杈剧导閸氼偊鏌涢悙鍨毈闁哄矉缍侀幃銏ゅ传閵夛箑娅戦梺璇插閸戝綊宕㈤崜褍鍨濋柛顐熸噰閸嬫捇鏁愭惔鈥冲箣闂佺顑嗛幐楣冨箟閹绢喖绀嬫い鎺戝亞濡差剛绱撻崒姘偓鍝ョ矓閹绢喗鏅濇い蹇撶墕杩濇繛杈剧悼绾爼寮告惔銊︾厵閻庣數顭堟禒婊堟煛鐎ｎ亜鈧灝顫忓ú顏勫窛濠电姴鍟ˇ鈺呮⒑閸涘﹥灏伴柤褰掔畺閳ワ箓宕稿Δ鈧粻锝嗙節闂堟稑鏆為柡鍌楀亾闂傚倷鐒︾€笛呯矙閹寸姭鍋撳鐓庡缂佸倸绉电缓浠嬪川婵犲嫬骞堝┑鐘垫暩婵挳宕悧鍫熸珷妞ゅ繐鐗婇幊姘舵煟閹邦垼姊跨憸鐗堝笚閺呮煡鏌涢顐簼缂傚秴鐗撳娲川婵犲嫭鍣х紓浣虹帛閿曘垹顕ｆ繝姘嵆闁靛繒濞€閸炶泛鈹戦悩鑼粵闁告梹鐗滈悷褏绱撻崒娆掑厡闁稿鎹囧畷鏇炵暦閸モ晝顦繝鐢靛Т濞层倝鎷戦悢鍏肩厽闁哄倸鐏濋幃鎴︽煟閹哄秶鐭欓柡灞诲姂瀵潙螖閳ь剚绂嶆ィ鍐╁€垫繛鍫濈仢閺嬨倝鏌涚€ｎ偅灏甸柟骞垮灩閳藉濮€閻樿鏁规繝鐢靛Т閿曘倝骞婇幇鐗堝亗闁瑰墽绮埛鎴︽煕濠靛棗顏柣鎺曟硶缁辨挸顓奸崟顓犵崲闂佺粯渚楅崳锝呯暦閸洦鏁嗛柍褜鍓氶崕顐︽⒒娴ｇ懓顕滄慨濠傤煼瀵煡顢曢妷锝勬睏闂佸憡渚楅崢鎼佸绩?
const isRouteChanging = ref(false)
const routeProgress = ref(0)
const isDarkMode = ref(false)
const THEME_KEY = 'theme'
const SIDEBAR_COLLAPSED_KEY = 'layout_sidebar_collapsed'
const SIDEBAR_WIDTH_STEP_KEY = 'layout_sidebar_width_step'
const sidebarWidthPresets = [160, 180, 200] as const
const minSidebarWidthStep = 0
const defaultSidebarWidthStep = 1
const maxSidebarWidthStep = sidebarWidthPresets.length - 1

const sidebarCollapsed = ref(false)
const sidebarWidthStep = ref(defaultSidebarWidthStep)
const isSidebarResizing = ref(false)
let sidebarResizeMoveHandler: ((event: MouseEvent) => void) | null = null
let sidebarResizeUpHandler: (() => void) | null = null

const normalizeSidebarWidthStep = (value: number) => {
  return Math.min(maxSidebarWidthStep, Math.max(minSidebarWidthStep, value))
}

const widthToStep = (width: number) => {
  let nearestStep = defaultSidebarWidthStep
  let nearestDiff = Number.POSITIVE_INFINITY

  sidebarWidthPresets.forEach((presetWidth, step) => {
    const diff = Math.abs(presetWidth - width)
    if (diff < nearestDiff) {
      nearestDiff = diff
      nearestStep = step
    }
  })

  return nearestStep
}

const getSidebarTargetWidth = () => {
  if (sidebarCollapsed.value) return 72
  return sidebarWidthPresets[sidebarWidthStep.value]
}

const sidebarAnimatedWidth = ref(getSidebarTargetWidth())
let sidebarWidthAnimationFrame: number | null = null

const stopSidebarWidthAnimation = () => {
  if (sidebarWidthAnimationFrame !== null) {
    cancelAnimationFrame(sidebarWidthAnimationFrame)
    sidebarWidthAnimationFrame = null
  }
}

const runSidebarWidthAnimation = () => {
  stopSidebarWidthAnimation()

  const animate = () => {
    const target = getSidebarTargetWidth()
    const current = sidebarAnimatedWidth.value
    const diff = target - current

    if (Math.abs(diff) < 0.5) {
      sidebarAnimatedWidth.value = target
      sidebarWidthAnimationFrame = null
      return
    }

    sidebarAnimatedWidth.value = current + diff * 0.18
    sidebarWidthAnimationFrame = requestAnimationFrame(animate)
  }

  sidebarWidthAnimationFrame = requestAnimationFrame(animate)
}

const sidebarCurrentWidth = computed(() => Math.round(sidebarAnimatedWidth.value))

const toggleSidebarCollapsed = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const loadSidebarPreference = () => {
  const savedCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
  if (savedCollapsed !== null) {
    sidebarCollapsed.value = savedCollapsed === '1' || savedCollapsed === 'true'
  }

  const savedStep = localStorage.getItem(SIDEBAR_WIDTH_STEP_KEY)
  if (savedStep !== null) {
    const parsedStep = Number.parseInt(savedStep, 10)
    if (!Number.isNaN(parsedStep)) {
      sidebarWidthStep.value = normalizeSidebarWidthStep(parsedStep)
    }
  }
}

const updateSidebarWidthByClientX = (clientX: number) => {
  const shellEl = shellRef.value
  if (!shellEl) return

  const shellLeft = shellEl.getBoundingClientRect().left
  const nextWidth = clientX - shellLeft
  const clampedWidth = Math.min(sidebarWidthPresets[maxSidebarWidthStep], Math.max(sidebarWidthPresets[minSidebarWidthStep], nextWidth))
  stopSidebarWidthAnimation()
  sidebarAnimatedWidth.value = clampedWidth
  sidebarWidthStep.value = widthToStep(clampedWidth)
}

const stopSidebarResize = () => {
  isSidebarResizing.value = false

  if (sidebarResizeMoveHandler) {
    window.removeEventListener('mousemove', sidebarResizeMoveHandler)
    sidebarResizeMoveHandler = null
  }

  if (sidebarResizeUpHandler) {
    window.removeEventListener('mouseup', sidebarResizeUpHandler)
    sidebarResizeUpHandler = null
  }

  if (!sidebarCollapsed.value) {
    runSidebarWidthAnimation()
  }
}

const startSidebarResize = (event: MouseEvent) => {
  if (sidebarCollapsed.value || event.button !== 0) return

  event.preventDefault()
  isSidebarResizing.value = true

  sidebarResizeMoveHandler = (moveEvent: MouseEvent) => {
    updateSidebarWidthByClientX(moveEvent.clientX)
  }

  sidebarResizeUpHandler = () => {
    stopSidebarResize()
  }

  window.addEventListener('mousemove', sidebarResizeMoveHandler)
  window.addEventListener('mouseup', sidebarResizeUpHandler)
}

watch(sidebarCollapsed, (collapsed) => {
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0')
})

watch([sidebarCollapsed, sidebarWidthStep], () => {
  if (isSidebarResizing.value) return
  runSidebarWidthAnimation()
})

watch(sidebarWidthStep, (step) => {
  localStorage.setItem(SIDEBAR_WIDTH_STEP_KEY, String(normalizeSidebarWidthStep(step)))
})

const applyTheme = (mode: 'light' | 'dark') => {
  const root = document.documentElement
  root.classList.toggle('dark', mode === 'dark')
  isDarkMode.value = mode === 'dark'
  localStorage.setItem(THEME_KEY, mode)
}

const initTheme = () => {
  const savedTheme = localStorage.getItem(THEME_KEY)
  if (savedTheme === 'light' || savedTheme === 'dark') {
    applyTheme(savedTheme)
    return
  }

  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  applyTheme(prefersDark ? 'dark' : 'light')
}

const toggleTheme = async (event?: MouseEvent) => {
  const newMode = isDarkMode.value ? 'light' : 'dark'
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  if (reducedMotion) {
    applyTheme(newMode)
    return
  }

  const triggerElement = event?.currentTarget
  if (!(triggerElement instanceof HTMLElement)) {
    applyTheme(newMode)
    return
  }

  const rect = triggerElement.getBoundingClientRect()
  const x = rect.left + rect.width / 2
  const y = rect.top + rect.height / 2

  // 婵犵數濮烽弫鍛婃叏閻戣棄鏋侀柛娑橈攻閸欏繘鏌ｉ幋锝嗩棄闁哄绶氶弻娑樷槈濮楀牊鏁鹃梺鍛婄懃缁绘﹢寮婚敐澶婄闁挎繂妫Λ鍕⒑閸濆嫷鍎庣紒鑸靛哺瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁绘劦鍓欓崝銈嗐亜椤撶姴鍘寸€殿喖顭烽弫鎰板川閸屾粌鏋庨柍璇查叄楠炲棜顦虫い鏂垮缁辨捇宕掑▎鎺戝帯婵犳鍠楅幐鎶藉箖濡警娼╅悹杞扮秿閿曞倹鐓曢柡鍥ュ妼閺嬨倝鏌ｉ妶鍌氫壕闂傚倷绀佸﹢閬嶅磻閹捐绠氶悘鐐跺▏濞戙垹围闁搞儮鏅濋敍婵囩箾鏉堝墽绋荤憸鏉垮暞缁傚秹鎮欓鍌滅槇闂佹眹鍨藉褍鐡繝鐢靛仩椤曟粎绮婚幘璇茬畺闁跨喓濮寸粈鍐┿亜韫囨挻鍣归柡瀣灥閳规垿鎮╃拠褍浼愰梺缁橆殔濡稓鍒掗崼銉ラ唶闁绘梻顭堝鍨攽閳藉棗鐏犳繛纭风節瀹曨偊鎼归崗澶婁壕閻熸瑥瀚粈鈧悗娈垮枛婢у酣骞戦姀鐘闁靛繒濮烽娲⒑缂佹ê濮囬柣蹇斿哺瀹曞疇顦寸紒杈ㄦ尰閹峰懐绮欏▎鐐闂備胶顭堥鍐磹濠靛宓侀柛鎰╁壆閺冨牆宸濇い鏃囧Г閻濇娊姊虹涵鍛汗閻炴稏鍎甸崺鈧い鎺戝暙閻ㄦ椽鏌℃担鍦濞ｅ洤锕幃娆擃敂閸曘劌浜剧憸蹇曟閹炬剚娼╅悹楦挎椤㈠懘姊虹憴鍕姸婵☆偄瀚划濠氬冀閵娿倗绠氶梺闈涚墕閸婂憡绂嶆ィ鍐┾拺鐎规洖娲ㄧ敮娑㈡煙閻熺増鎼愰柣锝囨焿閵囨劙骞掑┑鍥ㄦ珦闂備椒绱徊浠嬫嚐椤栫偞瀚冮悗锝庡枟閳锋帡鏌涚仦鍓ф噯闁稿繐鏈妵鍕敇閻愰潧鈪靛銈冨灪閻楃姴鐣烽妸褉鍋撳☉娅虫垵鈻嶉崶顒佲拺闂傚牊渚楀褍鈹戦垾铏枠闁糕晝鍋涢濂稿川椤忓懏鏉搁梻浣虹帛閿氱€殿喛鍩栧鍕礋椤栨稓鍘遍梺闈涚墕閹峰宕曢弮鈧幈銊︾節閸屻倗鍚嬮悗瑙勬礀閵堟悂骞冮姀銈呯畳闁瑰搫妫楁禍楣冩煙閻戞ɑ鈷掔痪鎯с偢閺岀喖鏌囬敃鈧弸娑樏归悪鍛洭缂佽鲸甯炵槐鎺懳熼懖鈺冩澖闂備浇顕栭崰鏇犲垝濞嗗精娑㈠礃椤缍婇悡顒勫箵閹烘柧绱欓梻浣筋嚃閸犳銆冮崨杈剧稏婵犻潧顑愰弫鍡涙煃瑜滈崜娆忓祫婵犵數濮甸懝鍓ф兜閳ь剟姊绘笟鍥у缂佸鏁婚幃锟犳偄閸忚偐鍘甸柡澶婄墕婢т粙宕氶幍顔藉仏婵鍩栭埛鎴︽煙閹澘袚闁轰線浜堕幃浠嬵敍濞戞ɑ璇炴繝纰樺墲閹告娊鐛幒妤€绠ｆい鎾跺枎閸忓﹪姊绘担鐟邦嚋缂佽鍊块獮濠傤吋閸℃瑧褰鹃梺鍝勬川閸犳挾寮ч埀顒勬⒑濮瑰洤鐏叉繛浣冲嫮顩烽柟鐑橆殕閻撴洟鏌″搴′簻闁宠鐗忛埀顒冾潐濞叉牕鐣烽鍐簷濠电偞鎸婚懝鎯洪敐澶婁紶婵°倕鎳忛埛鎺楁煕鐏炴崘澹橀柍褜鍓氶幃鍌氱暦閹邦収妲归幖杈剧悼閻掑吋绻涢幘鏉戠劰闁稿鎸婚〃銉╂倷瀹割喗鈻堥梺鎼炲妼婢т粙骞栭悙顒佸閻熸瑥瀚ㄦ禒銏ゆ⒑鏉炴壆顦﹂柛鐔告綑閻ｇ兘骞掗幋顓熷兊婵℃彃鏈悧妤勫€村┑鐘垫暩婵敻顢欓弽顓炵獥婵°倕鎳夐埀顒婄畵瀹曞ジ濡烽妷锔叫氶梻浣告惈缁嬩線宕㈤懖鈺侇棜闁割煈鍠掗弨浠嬫煟濡搫绾у璺哄閺岋綁骞樼捄鐑樼亪闂佸搫鐬奸崰鏍蓟閸ヮ剚鏅濋柍褜鍓熷绋库槈閵忥紕鍘遍梺鍝勫€归娆撳磿閺冨牊鐓涢悘鐐垫櫕鏁堥梺鍝勮閸斿酣鍩€椤掑﹦绉靛ù婊勭箘閹风娀鎮欓悜妯锋嫼闂佸憡绻傜€氼厼锕㈤幍顔剧＜閻庯綆鍋呯亸鎵磼閸屾稑娴柡浣稿暣瀹曟帒顫濇鏍ㄐら梺鑽ゅ枑缁矂鏌婇敐鍛殾闁瑰墎鐡旈弫瀣煃瑜滈崜娆擄綖韫囨拋娲敂閸曨偆鐛╁┑鐘垫暩婵挳宕导鏉戠煑闁糕剝鐟х壕钘壝归敐鍛棌婵″弶妞介弻鈩冩媴鐟欏嫬鈧劖顨ラ悙鏉戠伌濠殿喒鍋撻梺缁橈供閸嬪懘寮埀顒勬⒑鐠囨彃鍤辩紓宥呮缁傚秶鎹勬笟顖滃姺婵犵數濮村ú锕傚煕閹达附鍊甸柛锔诲幖鏍″銈冨劚椤︾増绌辨繝鍥舵晝闁挎繂娲﹂崚娑㈡倵鐟欏嫭绀冪紒璇插暣钘濋柣妤€鐗婇崕鐔兼煥濠靛棙绁紒鍗炲暱閳规垿鎮欑€涙ê闉嶉梺鑹邦潐閸庡磭鍙呴梺闈涚墕椤︻垶宕欓悩缁樼厽闁哄啫鐗婂▍婊呯磼鐠囧弶顥為柕鍥у楠炲洭鍩℃担杞版偅闂備礁鎼Λ娆撴偡閳哄懎钃熼柨婵嗩槹閺呮彃顭跨捄渚剱闁哄棛濮风槐鎾存媴閼恒儺浠╅梺鍝勬媼閸嬪棝宕氶幒鎴旀瀻闁规儳鍟块悗顓烆渻閵堝棙顥嗛柛瀣姍婵″爼顢氶埀顒€顫忔繝姘＜婵炲棙甯掗崢锛勭磽娓氬洤娅橀柛銊﹀閻忓绻涙潏鍓хɑ闁诡喖鐖奸崺鈧い鎺嶇缁椻晠鏌曢崶銊ュ妤犵偞甯￠獮姗€宕橀幓鎺嗘嫽婵犵绱曢崑鎴﹀磹閺囩姵宕查柟鎵閸嬪鈹戦悩鍙夋悙闁绘挻娲熼弻鐔兼倻濡儤顔呴悷婊呭鐢寮查弻銉︾厱妞ゆ劑鍊曞▍蹇撁归悩顐ｆ珚婵﹥妞藉Λ鍐ㄢ槈濞嗘ɑ顥ｉ梻浣瑰濞诧附绂嶉鍕靛殨閻犲洦绁村Σ鍫ユ煏韫囨洖啸妞ゆ梹甯￠弻锝嗘償閵婏附閿梺纭呭Г缁捇骞冮崸妤€绀嬫い鏍ㄧ▓閹锋椽鏌ｉ悩鍙夌闁逞屽墲濞呮洟鎮橀幘缁樷拺缂佸娉曠粻鏌ユ嫅閸楃們搴ㄥ炊瑜濋煬顒勬煙椤斿吋鍋ユい銏＄洴閺佹劙宕伴懜顒€鍔︽慨濠勭帛閹峰懏绗熼婊冨Ъ婵＄偑鍊栭崹闈浳涘┑瀣祦闁硅揪绠戦悙濠勬喐韫囨稑姹查柨鏃傚亾閸犳劙鏌ｅΔ鈧悧鍡樼┍椤栫偞鐓涘ù锝囶焾閺嗭綁鏌＄仦鐐鐎规洜鍘ч埞鎴﹀炊瑜庨鐘电磽閸屾艾鈧鎷嬮弻銉ョ柧闁绘ê妯婂鏍磽娴ｈ偂鎴炲垔閹绢喗鐓曟繛鎴烇公閺€濠氭煕鎼淬垺宕岄柡宀嬬秮閹瑩寮堕幋婵囩槗闂備胶顭堥鍛存晝閵堝鍋╅柣鎴ｆ缁犳盯鏌℃径濠勪虎闁哥偑鍔岄—鍐Χ閸℃ê鏆楅梺绋款儑閸犳牠骞冮崸妤€绀嬫い鏍ㄧ▓閹锋椽姊婚崒姘卞闁告娲熷畷濂稿Ψ閵壯勭叄婵犵數鍋為崹璺侯潩閵婏妇鈻旂€广儱妫涚粻楣冩煙鐎电浠ч柟鏂ュ亾濠电偛鐡ㄧ划宥囧垝閹捐钃熼柣鏂挎啞缂嶅洭鏌涢幘妤€鎯欓幋婵愭富闁靛牆鍟崝姘亜閿旇鐏︽繝鈧担绯曟斀闁绘顕滃銉╂煙閸愭彃顒㈢紒鍌氱Ч楠炲棝鈥栭妷銉╁弰鐎规洘鍎奸¨鍌炴椤掑澧柍瑙勫灴閸ㄦ儳鐣烽崶褏鍘介柣搴ゎ潐濞插繘宕濋幋锔衡偓浣糕枎閹惧磭顦х紒鐐緲瑜板宕Δ鍛拻?
  const { executeThemeAnimation, getAnimationConfig } = await import('@/composables/useThemeAnimation')
  const config = getAnimationConfig()
  
  // View Transitions API 婵犵數濮烽弫鍛婃叏閻戣棄鏋侀柛娑橈攻閸欏繘鏌ｉ幋锝嗩棄闁哄绶氶弻娑樷槈濮楀牊鏁鹃梺鍛婄懃缁绘﹢寮婚敐澶婄闁挎繂妫Λ鍕⒑閸濆嫷鍎庣紒鑸靛哺瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁绘劦鍓欓崝銈嗐亜椤撶姴鍘寸€殿喖顭烽弫鎰緞婵犲嫮鏉告俊鐐€栫敮濠勬媼閺屻儱鍑犳繛鍡樻尰閳锋垹绱撴担濮戭亞绮埡浣叉斀妞ゆ柨鎼埀顒侇殜楠炴垿濮€閻橆偅顫嶉梺闈涚箳婵挳鎳撻崹顔规斀闁宠棄妫楅悘銉︺亜閺囧棗鎳庨弸鍫⑩偓骞垮劚椤︿即鎮￠悢鍏肩厽闁哄倹瀵ч幉鎼佹煙閾忣偅绀堢紒杈ㄥ浮閹晠鎼归銏紦婵°倗濮烽崑娑㈠疮椤愩儳浜欓梻浣告啞娓氭宕板Δ鈧埢宥咁煥閸喓鍘甸梺鍏肩ゴ閺呯偠妫㈤梻浣告啞閹歌崵鎹㈤崼銉ョ畺婵☆垯璀﹂崥瀣熆鐠轰警鍎岄柟閿嬫そ濮婅櫣娑甸崨顓濇睏闂佺顑嗛惄顖炲春閳ь剚銇勯幒宥囧妽缂佲偓鐎ｎ喗鐓欐い鏍ㄦ皑閻掑摜鈧娲樼敮锟犲箖濞嗘挻鍤戦柤绋跨仛閸熸椽姊婚崒娆掑厡缂侇噮鍨伴～蹇旂節濮橆剛鍘遍梺鍓插亖閸庨亶寮告担琛″亾楠炲灝鍔氭い锔垮嵆閹繝寮撮姀锛勫帗闂佸疇妗ㄧ粈渚€寮搁妶鍡欑闁割偆鍣﹂懓璺ㄢ偓瑙勬处閸ㄥ爼鐛弽銊﹀闁稿繐顦扮€氬ジ姊婚崒娆戣窗闁稿妫濆畷鎴濃槈閵忊€虫濡炪倖鐗楃粙鎺戔枍閻樼偨浜滈柡宥庡亜娴狅箓鏌涙繝鍕毄缂佽鲸甯掕灃濞达綀銆€濡插牆鈹戦悙鑼勾闁稿﹥鐗犻妴浣圭節閸ャ劉鎷绘繛杈剧到閹诧繝宕悙瀵哥閻犲泧鍛殼閻庤娲樺姗€锝炲┑瀣殝闂傚牊绋愰惀顏堟⒒娓氣偓閳ь剛鍋涢懟顖涙櫠鐎涙ɑ鍙忓┑鐘叉噺椤忕娀鏌熼崣澶嬪唉鐎规洜鍠栭、鏇㈠Χ鎼粹懣鐐测攽閻樺灚鏆╅柛瀣洴钘濆ù鐓庣摠閸庡孩銇勯弽顐粶鏉╂繈姊虹粙璺ㄧ伇闁稿鍋ら獮鍡涙倷閻戞鍘遍梺鎸庢椤曆囩嵁濮椻偓閺屻劌鈽夊▎鎴犵暫缂備胶绮粙鎺戭焽韫囨稑绀堢憸蹇氭懌闂佽崵鍠愮划宥咁熆濮椻偓瀹曨垶顢涘鍛効閻庡箍鍎卞Λ搴ㄥ磻閸涘瓨鐓曢柟鑸妽閺夊綊鏌熼柨瀣仢婵﹥妞藉畷銊︾節閸曘劍顫嶉梻浣瑰濞插繘宕愰弽顓炵疄闁靛ň鏅滈弲婵嬫煕鐏炲墽銆掗柛姗€浜跺铏圭磼濡洘鍨垮畷婊冾潩椤戣姤鐏佸┑鐘诧工閻楀﹪鎮″▎鎰╀簻闁哄洨鍋為ˉ鐘电磼閳锯偓閸嬫捇鏌ｆ惔銏╁晱闁哥姵顨婇獮鎰板箮閽樺鐣洪梺闈涚箞閸婃牠骞嗛悙鐑樺仯闁搞儻绲洪崑鎾绘惞椤愶絿褰梻鍌氬€搁崐鎼佸磹閻戣姤鍤勯柛顐ｆ礀缁犵娀鏌熼悙顒併仧闁轰礁顑嗛妵鍕箻閸楃偟浠肩紒鐐劤椤兘寮婚敐澶婄睄闁稿本鑹炬禒妯肩磽娴ｅ搫啸濠电偐鍋撻梺鍝勬湰閻╊垰顕ｉ幘顔嘉╅柕澶堝劤椤旀帞绱撴担鐟板姢濠⒀傜矙瀵煡顢曢敃鈧悞鍨亜閹哄棗浜剧紓浣哄Т缁夌懓鐣烽弴銏犵闁绘劕绉电粙鎴ｇ亙闂佸憡渚楅崰鏍焵椤掆偓閻栧ジ寮婚悢铏圭＜闁靛繒濮甸悘宥夋⒑缂佹ɑ灏伴柣鈺婂灦楠炲啫顫滈埀顒勫箖濞嗘挸绠甸柟鍝勬鐎垫牗绻濋悽闈涗沪鐟滄澘鍟撮、姘额敇閵忕姷鍔﹀銈嗗笂缁讹繝宕箛娑欑厱闁挎繂楠稿▍宥団偓瑙勬礃缁矂鍩ユ径鎰潊闁绘ɑ顔栭崬鐢告⒒娴ｈ櫣甯涙い顓炵墦椤㈡俺顦寸紒顔碱煼閹粙宕ㄦ繝鍕箥闂備胶绮崹鍫曟晪濠殿噯绲界€氫即寮婚敓鐘茬倞闁靛鍎虫禒楣冩⒑閹惰姤鏁遍悽顖涘浮濠€渚€姊洪幐搴ｇ畵闁瑰啿绻樺畷顖炴倷閻戞鍘靛銈嗙墬濮樸劍鏅堕敃鍌涚厸鐎光偓鐎ｎ剛鐦堥悗瑙勬礀閵堟悂銆侀弴銏狀潊闁绘﹩鍋呯€氼剟姊婚崒娆愮グ妞ゆ洘鐗犲畷褰掑箥椤旂懓浜炬慨姗嗗亜瀹撳棝鏌曢崱鏇狀槮闁宠棄顦垫慨鈧柍銉︽灱閸嬫捇鎮滈懞銉㈡嫽闂佸壊鍋嗛崰鎾诲Υ閹烘鐓忛柛顐墰閻ｅ灚鎱ㄦ繝鍕笡闁瑰嘲鎳樺畷銊︾節閸涱垼鏀ㄩ梻鍌欒兌椤牏鑺卞ú顏勭９婵犻潧顑呰繚闂佸憡鍔﹂崰鏍ь啅濠靛洢浜滈柡宥冨妿閻棛绱掑Δ鈧ˇ闈涱潖濞差亜绠伴幖杈剧悼閻ｉ潧顪冮妶蹇曠窗闁告濞婇獮鍐晸閻樺啿浜滈梺绋跨箺閸嬫劙宕㈤悽鍛娾拻濞撴艾娲ゅ璺ㄧ磼閻樺啿鐏﹂柡鍛埣椤㈡盯鎮欑€电甯楃紓鍌氬€烽悞锕佹懌缂備讲鍋撻柛鎰╁墸鎼淬劌鐐婄憸婵嬬叕椤掑倵鍋撳▓鍨灈妞ゎ參鏀辨穱濠囨倻閽樺）褔鏌涢埄鍐炬畷闁诲繑鎹囧濠氬磼濞嗘埈妲梺鍦拡閸嬪﹪骞嗙仦鎯х窞閻忕偟鏅粵蹇斾繆閵堝繒鍒伴柛鐕佸亞缁顫濋懜鐢靛幐闂佸憡鍔戦崝搴㈡櫠閺囥垹鐐婇柟缁㈠枟閻撴瑩鏌涜箛姘汗闁哄棙锕㈤弻娑㈠Ω閵娿儱鎯炵紓渚囧枟濡啴寮婚妸褉鍋撻敐搴″闁伙箑鐗撳鍝勑ч崶褏浼堝┑鐐板尃閸曨収娴勫┑鐘诧工閹冲宕戦幘鏂ユ灁闁割煈鍠楅悘鍫ユ⒑缂佹澧柕鍫熸倐閻涱噣宕橀褎鈻岄柣搴㈩問閸犳骞愰搹顐ｅ弿闁逞屽墴閺屽秹宕崟顐熷亾閻熸壋鏋嶉柡鍐ㄧ墛閳锋帒霉閿濆洦鍤€妞ゆ洘绮庣槐鎺旀嫚閹绘巻鍋撻懗顖涱棨婵＄偑鍊栭悧妤冨垝鎼淬劍鍎楅柛鈩冪⊕閻撴洘銇勯幇鍓佹偧閻犳劏鏅濋幉鎼佹偋閸繄鐟查梺鍝勬噺閻擄繝寮诲☉銏╂晝闁靛牆鎳忛悵鈩冪箾鐎电袥闁哄懐濮撮～蹇涙惞閸︻厾锛滃┑鈽嗗灥椤曆囨瀹ュ鈷戦悷娆忓閹藉啰鈧娲滈弫濠氱嵁閹达箑顫呴柣姗嗗亝閺傗偓闂佽鍑界紞鍡樼鐠轰警鐒藉┑鐘叉处閳锋垿鏌熺粙鎸庢崳缂佺姵鎸绘穱濠囶敃閿濆洦鍒涙繝纰樺墲閹告娊鐛崶顒夋晢濠㈣泛顑呴惁婊堟⒒娓氣偓濞佳囨偋閸℃あ娑樜旈崨顔尖偓鍫曟煏婢舵稑顩紒鐘荤畺閹﹢鎮欓幓鎺嗗亾閸涘﹣绻嗛柛蹇曨儠娴滄粓鏌￠崶鏈电敖缂佸鍓氶妵鍕晝閳ь剛绱炴繝鍥ц摕婵炴垯鍨归悡姗€鏌熼鍡楀€搁ˉ姘節绾板纾块柛瀣灴瀹曟劙寮借閸熷懎鈹戦悩瀹犲缁炬儳顭烽弻鐔煎礈瑜忕敮娑㈡煟閹惧啿鏆ｉ柟顔煎槻閳诲氦绠涢幙鍐ф偅闂備浇顕х换鎰版偤閵娾晛桅闁告洦鍨伴～鍛存煥濞戞ê顏柛锝勫嵆濮婅櫣鎷犻垾宕囦哗闂佹椿鍘奸崐鍧楀Υ娓氣偓瀵挳濮€閳哄倹娅囬梻浣芥硶閸犳挻鎱ㄧ€涙顩烽柟鎵閻撶喖骞栧ǎ顒€鈧倕顭囬幇顓犵闁圭粯甯炵粻鑽も偓瑙勬礃濞茬喖鐛惔銊﹀癄濠㈣泛鑻慨锔戒繆閻愵亜鈧牜鏁幒妤佹櫇闁挎柨澧介惌鎾绘煟閵忕姵鍟為柣鎾冲暟閹茬顭ㄩ崼婵堫槶闂佹寧娲栭崐鎼佸垂閸岀偛绾ч柛顐ｇ濞呭棝鏌￠崱妯肩煉闁哄瞼鍠栭幃婊冾潨閸℃鏆﹂梻浣侯焾椤戝倿寮插鍛床婵犻潧顑嗛ˉ鍫熺箾閹存繂鑸归柛鎾村缁辨挻鎷呴幓鎺嶅闂佽鍑界紞鍡涘磻娴ｅ湱顩叉繝濠傜墛閻撴瑩寮堕崼婵嗏挃闁告帗澹嗛幃顔碱潩閼哥數鍘介柟鍏肩暘閸ㄥ吋绔熷鈧弻鏇㈠醇閵忊晝鍔稿銈庡亜缁绘帞妲愰幒鎳崇喓鎷犲顔瑰亾閹剧粯鈷戦柛娑橈功閳藉鏌ㄩ弴妯哄婵炴垹鏁婚崺鈧い鎺嶆缁诲棝鏌ｉ幇鍏哥盎闁逞屽厵閸婃繂鐣烽姀锛勯檮闁告稑锕ゆ禍閬嶆⒑缁洖澧茬紒瀣笧缁骞掑Δ浣叉嫽婵炶揪缍€濞咃絿鏁☉銏＄厱闁靛ě鍐ㄤ粯闁捐崵鍋ら弻娑㈠即閵娿儳浠梺绋款儏閸婂潡寮诲澶娢ㄩ柨鏇楀亾濠⒀屽灦閺岋綁寮幐搴＆闂佸搫琚崐婵嬬嵁閺嶃劍濯撮悷娆忓閺侇亜鈹戦悩鎰佸晱闁哥姵鐗犻幃褔骞樼拠鑼舵憰闂佹寧绻傞ˇ顖滅不婵犳碍鍋ｉ柧蹇氼潐绾绢亪鏌ㄥ┑鍡樺窛缁炬崘鍋愮槐鎾存媴鐠囷紕鍔峰┑鐐插级閹告娊寮婚悢椋庢殾闁搞儺鐏濋敐澶嬬叆婵炴垶鐟ユ慨鍥煃鐟欏嫬鐏寸€规洖宕～婊堝幢濡や焦娈洪梻鍌氬€搁崐鎼佸磹瀹勬噴褰掑炊椤掑鏅悷婊冮叄閵嗗啴濡烽妸褏鏉搁梺鍝勫€告晶鐣岀不濮樿埖鈷戦柟鑲╁仜閸旀挳鏌涢幘瀵告噰闁诡喚鍋ゅ畷褰掝敃閻樿京鐩庨梻浣告贡閸庛倝宕归悽绋垮嚑闁靛牆妫涚粻楣冩煕韫囨洖甯跺┑顔肩墢缁辨帞绱掑Ο灏栨闂傚洤顦甸幃妤呮晲鎼粹€茬凹闂佺粯绻冮悧婊呮閹惧瓨濯撮柟瀛樺笒閹牓姊虹粙娆惧剳闁稿鍠撻崚鎺楊敇閵忊€充簻闂佺粯鎸稿ù鐑藉礉閿曗偓椤啴濡堕崱妤冪懆闁诲孩鍑归崰鏍偩閸偆鐟归柍褜鍓熷璇测槈閵忕姷鐤€闂佸疇妗ㄧ粈浣告暜闂傚倷绀侀幖顐︻敄閸涘瓨鐓€闁挎繂顦拑鐔兼煟閺冨倸甯堕柛銊ュ€归妵鍕棘閸喗鍊┑鐐茬墛閻撯€愁潖濞差亜浼犻柛鏇ㄥ墮濞咃繝姊洪幖鐐插婵☆偄瀚伴敐鐐剁疀濞戞瑦鍎梺闈╁瘜閸橀箖鎮￠幘缁樷拺闁稿繒鍘ф晶顖炴煕閵娧冨付妞ゎ厼娲畷濂稿即閻斿弶瀚肩紓鍌欑椤戝懐浜搁崨鏉戠哗濠电姵纰嶉悡鐔镐繆閵堝嫯鍏岄柣顓炵焸閺屾盯骞掗幘宕囩懖缂備胶绮换鍫濈暦閸洘鍤嬮柛顭戝亝閻濇牠姊婚崒娆戝妽閻庣瑳鍏炬稒鎷呯粵瀣瘞闂傚倷绀佺紞濠囁夐幘璺哄灊妞ゆ牗绮嶅畷鍙夌箾閹寸偟鎳勭紓宥呮喘閺屾盯骞樺Δ鈧崯顐︽偂閸岀偞鈷掑ù锝勮閺€鐗堛亜閺囩喓鐭岄柟骞垮灩閳规垹鈧綆鍓欑粊锕傛⒑缁洖澧茬紒瀣灴閺屽宕堕浣哄帾婵犮垼鍩栫粙鎾绘偩閸楃伝褰掓偑閳ь剟宕圭捄渚綎婵炲樊浜滅粻褰掓煟閹邦厼绲诲┑顔碱樀濮婃椽宕崟顒€娅ょ紓浣割儐鐢偟鍒掔€ｎ喖绠抽柟鎯ь嚟缁夊爼姊虹€圭媭娼愰柛搴ゆ珪缁傚秵銈ｉ崘鈺佷画濠电偛妫楃换鎰邦敂椤忓棛纾奸柍褜鍓熷畷姗€顢欓悾灞藉汲闂備礁鎼ú锕傛晪闂佽绻嗛弲鐘诲蓟閿濆鏅查柛娑卞幗浜涙俊鐐€ら崑鍛垝閹捐鏄ラ柍褜鍓氶妵鍕箳閹存繍浠奸梺鍝勫閸庣敻寮诲澶婄厸濞达絽鎲″▓鍓佺磽娴ｅ弶顎嗛柛瀣崌濮婄粯鎷呴崨濠傛殘闂佸憡妫戦梽鍕矉瀹ュ應鏀介柛鈾€鏅濋崬鐢告⒑閸︻厼鍔嬫い銊ユ閸╂盯骞掑Δ浣哄幈闁诲繒鍋涙晶浠嬪箠閸涱喓浜滈柨鏃囧亹閻ｇ敻鏌″畝鈧崰鎾诲窗婵犲洤纭€闁绘劖婢橀弸鍫ユ⒒娴ｇ瓔鍤冮柛銊ゅ嵆瀵敻顢楅埀顒勵敋閵夆晛绀嬫い鎰╁€栧▓鏇㈡⒑闁偛鑻晶鎵磼椤旇偐澧涚紒缁樼箞瀹曟垿顢涘杈┬ㄩ梺杞扮劍閸旀瑥鐣锋總鍓叉晝闁挎繂娲ㄥ暩闂傚倸鍊风粈渚€骞夐敓鐘冲仭闁靛／鍕簥濠殿喗銇涢崑鎾垛偓娈垮枦椤曆囶敇婵傜閱囨い鎰剁秵閳ь剙娲缁樻媴閸涘﹤鏆堥梺瑙勬倐缁犳牕鐣锋导鏉戝唨鐟滄粓宕甸弴鐐╂斀闁绘ê纾。鏌ユ煛閸涱喚鍙€闁哄本绋戦埥澶愬矗濡厧鍤梻浣筋嚙妤犳悂鈥﹂悜钘夎摕闁挎繂鐗忛悿鈧梺鍝勬川閸嬫ê鈻介鍫熲拺闁硅偐鍋涙俊鐣岀磼鐠囨彃鏆熺紒顔规櫊閹垽鎮℃惔鈥崇ギ闂備線娼х换鍡楊瀶瑜旈獮蹇曠磼濡偐顔曢柡澶婄墕婢х晫绮旈浣虹闁告粌鍟伴幃濂告煛娓氬洤鏋涢柍钘夘樀婵偓闁挎稑瀚獮宥夋⒒娴ｅ憡鍟炵紒瀣灴閺佸啴濡烽埡浣猴紮闂佸綊鍋婇崰鎺楀磻閹捐埖鍠嗛柛鏇ㄥ墰閿涙﹢姊虹粙鍨劉濠电偛锕畷娲焵椤掍降浜滈柟鐑樺煀閸旂喓绱掓径灞炬毈闁哄本鐩獮妯煎鐎ｎ亶妫熼梻浣风串缁插潡宕楀Ο铏规殾闁挎繂妫楃欢鐐碘偓鍏夊亾闁逞屽墴椤㈡瑩寮撮姀鈾€鎷洪梺鑽ゅ枑婢瑰棝骞楅悩缁樼厽闁绘梹娼欓崝锕傛煙椤旀枻鑰块柛鈺嬬節瀹曟﹢顢旈崱顓犲簥闂傚倷鑳剁划顖炴晪濠碘槅鍨伴敃顏堝箖閳╁啰闄勯柛娑橈功閸樻悂鏌ｈ箛鏇炰粶濠⒀嗘鐓ら悗娑欙供濞堜粙鏌ｉ幇顒€绾ч柛鐘成戦妵鍕閳藉棙鐣烽梺鐟板槻閹虫ê鐣烽敐鍡楃窞閻忕偠鍋愰弫鏍⒒閸屾艾鈧悂宕愭搴ｇ焼濞撴埃鍋撴鐐寸墵椤㈡洟鍩楅懞銉р姇闁诡垱妫冩俊鎼佸Ψ閵壯€鍋撻銏♀拺闁兼亽鍎嶉鍩跺洭鎸婃径妯煎姺闂佸搫绋侀崢浠嬫偂閿濆鍙撻柛銉ｅ妼閸ゎ剚绻涢崗鐓庡闁哄本绋栫粻娑㈠籍閸屾粎鍘滈梻浣告惈閺堫剛绮欓幋锕€鐓″鑸靛姇绾偓闂佺粯鍔樼亸娆擃敊閹烘挾绡€婵炲牆鐏濆▍娆戠磼閹绘帩鐓肩€规洖缍婇幖鍦喆閸曨偄绨ユ繝鐢靛█濞佳囶敄閸涘瓨鍋傞柡鍥ュ灪閻撳啰鎲稿鍫濈闁绘棃顥撻弳锕傛煟閺冨倸甯堕柛銊ュ€归妵鍕箛閳轰讲鍋撻弽褜鐔嗛柟鐑樺灍閺€浠嬪箳閹惰棄纾规俊銈勭劍閸欏繘鏌ｉ幋锝嗩棄缁惧墽绮换娑㈠箣閻愭鏆￠悗瑙勬礀瀵埖绌辨繝鍥舵晬婵犻潧娴傛禒鈺呮⒑閸濆嫭锛旂紒鐘虫崌瀵寮撮悢铏诡啎閻熸粌顦靛畷鎴﹀箻缂佹鍘遍柣搴秵閸嬪懐浜搁銏＄厓闁芥ê顦藉Σ鎼佹煃鐠囪尙效妞ゃ垺顭堥ˇ杈╃磼閵娿劌浜圭紒杈ㄥ浮瀹曟帒鈽夊Ο鏄忕檨婵＄偑鍊戦崹娲晝閵忊剝鍙忛柍褜鍓熼弻宥夋煥椤栨矮澹曢梻浣哥秺椤ユ挾鍒掗婊勫床婵炴垯鍨圭粻鑽ょ棯閹屽剰妞ゃ儲绻傞埞鎴︽倷閼碱剚鍕鹃梺绋匡攻濞茬喖銆佸鑸垫櫜濠㈣泛锕弫婊冣攽鎺抽崐鎾舵媼閺屻儱绠┑鐘崇閳锋垿鏌涘☉姗堟敾濠㈣泛瀚伴弻娑氣偓锝庝簻椤忣厽銇勯姀鈩冾棃闁糕晪绻濆畷鎺懳熼崷顓犳晨濠碉紕鍋戦崐鏍箰妤ｅ啫纾婚柣鎰惈绾惧鏌曟径娑樼槣婵炲牅绮欓弻锝夊箛椤撶喓绋囩紓浣诡殕鐢繝骞楅崼鏇炲唨妞ゎ兘鈧磭绉洪柡浣瑰姍瀹曘劑顢橀悩鑽ゅ礈闂備浇顕х€涒晜绌遍崫鍕庢盯宕熼姘卞幋闂佺鎻梽鍕磹閻戣姤鐓犻柟闂寸劍濞懷勭箾閹冲嘲鎳愮壕钘壝归敐鍫燁棄缂佹唻濡囩槐鎺楊敊閻ｅ本鍣伴梺缁樹緱閸犳顕ラ崟顖氱疀妞ゆ挾鍠愰鐔兼⒒娴ｈ櫣甯涙い顓炵墢娴滅鈻庨幘瀹犳憰闂佸壊鍋侀崕鏌ュ煕閹寸姷纾藉ù锝咁潠椤忓懏鍙忓鑸靛姈閻撴洟骞栫€涙鈽夐柍褜鍓氱换鍫ョ嵁閸愵喖鐏抽柡鍌樺劜椤秴鈹戦鏂ゅ叕缂佽尪濮ょ粋宥嗐偅閸愨晝鍘遍棅顐㈡处閹尖晛危缁嬫５鐟邦煥閸垻鏆梺鍝勭焿缁查箖骞嗛弮鍫晬婵犲﹤鎲涢敐澶嬧拺闁告稑锕ョ亸鎵磼鐎ｎ偆澧甸柛鈺佹嚇閹粙宕ㄦ繛鐐闂佽崵濮村ú銈咁嚕閸洖鑸瑰璺侯儍娴滄粍銇勯幇鈺佺労婵″弶鎮傞幃锟犲Χ閸℃洜绠氬銈嗙墬閼归箖骞冮幋鐘亾鐟欏嫭绀冮柣鎿勭節瀵鈽夊Ο鍏兼畷闂侀€炲苯澧寸€规洘鍨块幃娆撳传閸曨叏绱遍梻浣稿暱閹碱偊宕愰懡銈呭К闁逞屽墴濮婂宕掑鍗烆杸婵炴挻纰嶉〃濠傜暦閺囷紕鐤€闁哄洨濮烽敍婊堟⒑闁偛鑻晶浼存煃瑜滈崜銊х礊閸℃稑纾诲ù锝呮贡椤╁弶绻濇繝鍌滃闁绘挻鐟╅弻鐔告媴閸愨晝褰у┑鐐叉噹閹虫﹢寮婚敐鍫㈢杸闁挎繂鎳忛悵婵嬫⒑閸濆嫯瀚扮紒澶屽厴绡撳〒姘ｅ亾闁哄本鐩獮娆撳礋椤撶姵娈奸柣搴ゎ潐濞测晝绱炴担鍝ユ殾婵せ鍋撳┑鈥虫啞閹棃濮€閵忊€冲灡闁诲氦顫夊ú蹇涘礉閹达妇宓侀柡宥庡弾閺佸洭鏌ｉ弬鎸庡暈闁绘繃鐗犲濠氬磼濞嗘垹鐛㈠┑鐐板尃閸涱喖搴婇梺绯曞墲缁嬫垿鎮為崹顐犱簻闁瑰搫绉堕ˇ锕€顭胯閸ㄨ鲸绌辨繝鍥ㄥ殤闁哄牓娼ч幆鍫㈢磽娴ｄ粙鍝洪柟鐟版搐閻ｇ兘骞掗幋鏃€鐎婚梺瑙勬儗閸樺€熲叺婵犵绱曢崑鎴﹀磹閺嶎厼鍨傞梻鍫熷厷濞戞ǚ鏀介柛鈩冪懄濞堥箖鎮峰鍛暭閻㈩垱甯￠獮鎴︽嚋閻愰€涚盎闂佽宕樺▔娑欑濠婂牊鐓?
  if (config.type === 'view') {
    const root = document.documentElement
    root.classList.add('view-transitioning')
    isDarkMode.value = newMode === 'dark'
    localStorage.setItem(THEME_KEY, newMode)
    try {
      await executeThemeAnimation({ x, y, reducedMotion })
    } finally {
      root.classList.remove('view-transitioning')
    }
  } else {
    // 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鏁愭径濠勵吅闂佹寧绻傞幉娑㈠箻缂佹鍘遍梺闈涚墕閹冲酣顢旈銏＄厸閻忕偛澧藉ú瀛樸亜閵忊剝绀嬮柡浣瑰姍瀹曞崬鈻庡▎鎴犫敍闂傚倸鍊风欢姘跺焵椤掑倸浠滈柤娲诲灡閺呭爼宕滆绾惧ジ鏌ｅΟ鎸庣彧閻忓浚鍙冮弻锝夋晲婢跺鏆犵紓浣芥閺咁偆鍒掑▎蹇婃瀻闁绘劦鍓涚粔閬嶆⒒閸屾瑨鍏岄柛瀣ㄥ姂瀹曟洟鏌嗗鍛焾闁荤姵浜介崝蹇旀叏閹惰姤鐓忓璺烘濞呭棝鏌嶉柨瀣瑨闂囧鏌ㄥ┑鍡樻悙闁告柨顑夐弻娑㈠Χ閸屾矮澹曢梻鍌氬€风粈渚€顢樻禒瀣骇闁割煈鍣悗鐑芥⒒娴ｇ儤鍤€缂佺姴绉瑰畷瑙勭鐎ｎ剙绁﹂梺鎼炲労閸撴岸宕戠€ｎ喗鐓曟い鎰剁悼缁犳牠鏌ｉ敐搴″⒋婵﹦绮幏鍛瑹椤栨稓绉洪梻浣告啞濞叉牠鎮樺鑸靛仼闁绘垼濮ら埛鎴犵磽娴ｈ偂鎴犱焊閻楀牏绠鹃柤纰卞墮閺嬫稓鈧鍠栭…閿嬩繆閹间礁鐓涘ù锝堟濞煎姊绘担瑙勫仩闁稿孩娼欓埢鏂库槈濡攱鐏佸銈嗘尵閸婏綁寮崼鐔蜂汗闂傚倸鐗婄粙鎰柦椤忓牊鈷戠紓浣癸供濞堟ê鈹戦悙鈺佷壕闁诲孩顔栭崰娑㈩敋瑜旈崺銉﹀緞閹邦剦娼婇梺缁樕戦悧鎴﹀疾閻樿钃熼柕濞炬櫅濡﹢鏌涢…鎴濇灀闁圭鍟村鐑樺濞嗘垹蓱濠碉紕鍋犲Λ鍕綖韫囨拋娲敂閸滀焦顥堟繝鐢靛仦閸ㄥ爼鎮烽敃鍌氱畺婵炲棙鎸婚悡鐔煎箹濞ｎ剙鐏柣鎿冨灦閺屾稑螖娴ｇ硶鏋欓梺璇″枙閸楁娊銆佸璺虹劦妞ゆ帒瀚畵渚€鏌熼悜妯烘闁哄啫鐗嗛悞鍨亜閹烘垵鈧粯绋夊澶嬬叆婵犻潧妫欓ˉ鐘电磼閳锯偓閸嬫捇姊绘担绋款棌闁绘挸鐗撳畷鎴﹀礋椤掍礁寮块梺鍛婂姦閸犳鎮″▎鎰╀簻闁哄洨鍋為ˉ鐘绘煙椤斿灝浜圭紒杈ㄥ笚濞煎繘濡搁敃鈧壕鎶芥倵鐟欏嫭绀冮悽顖涘浮閸┿垺鎯旈妸銉ь唺濠电娀娼уΛ娆撳汲椤撱垺鈷掗柛灞剧懆閸忓本銇勯鐐靛ⅵ妞ゃ垺鐗犲畷鍗炩槈濡⒈鍞堕梻浣哥秺濡法鎷嬮弻銉ョ劦妞ゆ帒锕﹂悾鐢碘偓瑙勬礈椤牐鐏冩繛杈剧到閹诧繝鎮块崒鐐粹拻闁稿本鑹鹃埀顒佹倐閹勭節閸曨厾鐓撻梺纭呮彧鐠侊絿绱為弽顐熷亾楠炲灝鍔氭い锔垮嵆閸╂盯骞嬮悩鐢碉紳婵炶揪缍€閸嬪倿骞嬮悩杈╁墾濡炪倖鎸炬慨椋庡閼测晝纾藉ù锝咁潠椤忓懏鍙忕€广儱顦伴悡鏇㈡煃閸濆嫬鏆欏ù鐘洪哺椤ㄣ儵鎮欏顔煎壎闂佽桨绀侀崐鍧楀箰婵犲啫绶為柛鈩冦仦婢规洟姊虹紒妯虹伇濠殿喓鍊濋幃鈥斥枎閹炬潙鈧灚绻涢幋鐐垫噽闁绘帞鏅槐鎺楁偐閾忣偄纾抽梺鍝勭焿缁绘繂鐣烽崡鐐嶇喖宕楅悡搴㈢彫闂傚倷绶氬褍煤閵堝洠鍋撳鐓庣仯缂侇喛顕ч埥澶愬閳╁啯鐝抽梻浣告啞濞诧箓宕㈡總绋垮惞妞ゆ帒瀚埛鎺戙€掑锝呬壕闂侀€炲苯澧紒瀣崌閸╃偤骞掑Δ浣哄幈闂佸搫鍟犻崑鎾绘煕閵娿儳浠㈡い鏇秮椤㈡洟鏁冮埀顒傜不濞戙垺鐓涘璺猴功娴犮垻绱掗幇顓犳创婵﹥妞藉畷顐﹀礋閸倣褔姊洪幖鐐插闁轰浇顕ч悾鐑芥晲閸℃瑧鐦堥梺鍛婂姦娴滅偤鎯侀崼婵冩斀闁绘劘灏欐晶鏇㈡煟韫囨梻绠炵€殿喚顭堥埥澶愬閿涘嫬寮抽梻浣告惈濞诧箓鏁嬮梺鍛婃⒐绾板秹濡甸崟顖ｆ晜闁告洦鍋呭▓鑼磽娴ｇ鈧湱鏁悙鍝勭劦妞ゆ帒锕︾粔鐢告煕閹惧鎳呯紒顔硷躬閺佸啴宕掑☉鎺撳闁荤喐绮庢晶妤冩暜閹烘挾顩插ù鐓庣摠閻撴洘淇婇姘础闁活厽鐟ч埀顒冾潐濞叉ê煤閻旂厧绠栭柕蹇嬪€曠粈鍌炴煠濞村娅呯€殿喛娅曠换婵嬫偨闂堟稈鏋呭┑鐐板尃閸忕偓绋戣灃闁告侗鍘鹃崝锕€顪冮妶鍡楃瑐闁绘帪绠撳畷鎰板箛閻楀牏鍙嗗┑鐘绘涧閻楀棙绂掑鍫熺厽闁挎繂妫涚粻鐐碘偓瑙勬礈閸犳牠銆侀弽顓熷殟闁靛鍎烘导婊冣攽閻樺灚鏆╅柛瀣█楠炴捇顢旈崱娆戭槸闂侀€炲苯澧ǎ鍥э躬椤㈡洟濮€閻欌偓娴煎啴鏌﹀Ο鐓庢灁闁逞屽墮缁犲秹宕曢崡鐐嶆稒鎯旈姀銏╂锤濠电姴锕ょ€氥劍绂嶅鍫熺厵闁逛絻娅曞▍鍛存煟閹烘柨鍔嬪ǎ鍥э躬椤㈡稑螖閳ь剚绂嶆ィ鍐┾拺閻犲洤寮堕崬澶嬨亜椤愩埄妲搁悡銈嗕繆椤栨哎鍋ㄦ繛宸簼閸嬪嫰鏌ゅù瀣珔缂佷緤绠撻弻鐔煎礂閼测晜娈梺鍛婃煥缁夌懓鐣烽棃娑卞悑濠㈣泛顑囬崢顏呯節閵忥絽鐓愰柣鈺婂灠椤﹪顢氶埀顒勫蓟閿濆應鏀介柛銉㈡櫅閳峰苯鈹戦纭峰姛缂侇噮鍨崇划顓㈡偄閻撳海鍔﹀銈嗗坊閸嬫挻銇勯鐐寸┛妞わ附鎸抽弻鐔肩嵁閸喚浼堥悗瑙勬礀閵堝憡淇婇悜钘壩ㄧ憸婵堟椤曗偓濮婄粯绗熼埀顒€顭囪閹囧幢濞存澘娲、娑㈡倷閹绘帒娈ゅ┑鐐存尰閸╁啴宕戦幘缁樼厸閻忕偛澧介埥澶愭煟閿濆棛绠為柛鈹惧亾濡炪倖甯掔€氼剛澹曟繝姘厽闁归偊鍠栭崝瀣煕鐎ｎ亜鈧潡寮婚敓鐘茬倞闁宠桨鐒﹂悗顓熺箾鐎涙鐭嬬紒顔芥崌瀵鎮㈤悡搴ｉ獓闂佸壊鐓堥崳顕€寮抽姀銈嗏拺閻犲洠鈧櫕鐏曢梺绋款儐閸旀危閹版澘绠虫俊銈勭娴滃綊姊洪悷鎵憼闁告梹鐗犲畷褰掑箰鎼存繄绠氶梺姹囧灮椤牏绮堢€ｎ偁浜滈柡宥冨妿閳洘绻涢崨顓燁棦闁哄矉缍侀幃鈺呭矗婢跺鍊烽柣搴㈩問閸犳牠鎮ユ總绋跨畺闂傚牊绋堥弨浠嬫煕閳ュ磭绠查柡鍌楀亾濠碉紕鍋戦崐鏍ь潖婵犳艾违閻庯綆鍠栫紒鈺冪磽娴ｅ鑲╂崲閸℃稒鐓熼柟閭﹀灠閻撴劖銇勯妷銉█闁硅棄鐖奸幃娆撴倻濡厧骞堥梻浣筋潐婢瑰棝寮幖浣稿偍闁瑰濮甸崰鎰版煟濡も偓閻楀棛绮幒妤€鐐婇柟缁㈠枟閳锋垹绱掗娑欑濠⒀勭叀閺岋綁鎮ら崒婊呮殼閻庤娲橀懝楣冨煡婢舵劕顫呴柍銉︽灱閸嬫捇鎮介崨濠備画濠电偛妫楃换鎰邦敂椤忓棛纾奸柍褜鍓熷畷濂稿Ψ閿旀儳骞堥梻浣虹帛閿氱痪缁㈠幗閺呭爼鎮介崨濠勫帾闂佺硶鍓濆ú婊埶囬敃鍌涙嚉闁哄稁鐏愯ぐ鎺撴櫜闁搞儯鍔屽▓灞筋渻閵堝懎顒㈤柟鐟版搐椤繘鎼归崷顓狅紲濠碘槅鍨靛▍锝嗙缁嬫娓婚柕鍫濋楠炴牠鎮楀顓熺凡妞ゆ洩缍侀、妤佹媴閻熸澘濡抽梻浣筋潐閸庢娊鎮洪妸鈺佺骇闁归棿鐒﹂埛鎺懨归敐鍫燁仩閻㈩垱鐩弻銊ヮ潩閼哥數鍘介棅顐㈡处閺屻劑宕搹鍏夊亾濞堝灝鏋熷┑鐐诧躬瀹曟椽鏁撻悩鎻掔獩濡炪倖姊归崕鎶界嵁閸儲鈷戦悹鍥ㄥ絻閸よ京绱撳鍛棦鐎规洘绮岄埢搴ㄥ箛椤曞懏绁梺鍝勵槸閻楀啴寮笟鈧畷鎴﹀箻閼搁潧鏋傞梺鍛婃处閸撴盯藝閵壯呯＝闁稿本姘ㄥ瓭闂佹寧娲忛崐婵嬪箖妤ｅ啯鐓ラ悗锝庡墴濡绢喚绱撴担鍓插剰闁诲繑绻傞悾鐢稿幢濞戞瑢鎷虹紓鍌欑劍閿氬┑顔肩墛閵囧嫰寮埀顒勬偋閻樿尙鏆︽い鏍仜閻愬﹥銇勯幒宥堫唹闁归绮换娑欐綇閸撗勫仹濡炪値鍘奸悧鎾愁嚕閹惰姤鐒肩€广儱妫涢崢鐢电磼閻愵剚绶茬€规洦鍓氱粋宥夋偋閸偅顔旈梺缁樺姌椤曟粓寮ㄦ繝姘厵妞ゆ牗绋掗ˉ鍫濃攽閳╁啯鍊愰柡浣稿暣閸┾偓妞ゆ帒瀚粈鍫ユ煟閻旂顥愰柡鈧禒瀣闁规儼妫勭壕褰掓煛閸ャ儱鐏╃紒鐘靛█閻擃偊宕堕妸褉濮囬梺绋款儏閸婂潡寮婚敓鐘茬倞闁靛鍎虫禒楣冩⒑缂佹ɑ灏伴柣鐔叉櫊瀵鎮㈤崨濠傤€撻梺鍛婂姀閺呮繆銇愯閳规垿鎮欓崣澶婃闂佺懓鍟块柊锝夊灳閿曞倸閿ゆ俊銈勭娴狀參姊虹紒姗嗘當闁绘绮岃灋闁挎稑瀚壕钘壝归敐鍫燁仩閻㈩垱鐩弻锝夊煛婵犲倻浠搁梺缁樹緱閸犳岸鍩€椤掑﹦绉靛ù婊勭墵瀵憡鎯旈妸褍褰勯梺鎼炲劘閸斿秶澹曟繝姘厵妞ゆ洖妫涚粔顔芥叏婵犲偆鐓肩€规洘甯掗埢搴ㄥ箛椤斿搫浠掗梻鍌欐祰濞夋洟宕伴崱娑樼？闂傚牊绋撻弳锕傛煙閻楀牊绶查柛鎰ㄥ亾闂備線娼ц噹闁逞屽墴瀵劑鎼归銈囩槇闂佹眹鍨藉褍鐡繝鐢靛仜閻即宕愰弴鐏绘椽宕稿Δ浣叉嫽婵炶揪绲肩拃锕傛倿妤ｅ啯鐓涢柛顐亜婢ф挳鏌熼姘辩劯妞ゃ垺鐟╅幃鎯х暆閳ь剝銇愭ィ鍐┾拺闁告繂瀚婵嗏攽椤曗偓椤ユ挻绔熼弴鐔侯浄閻庯綆鍋嗛崢閬嶆煟韫囨洖浠滃褌绮欓獮濠囧幢濡晲绨婚梺鍝勫€归娆徫熼埀顒勬⒑閸濆嫭婀扮紒瀣崌閸┾偓妞ゆ帒锕︾粔鐢告煕鐎ｎ亝鍣归柣锝呭槻閻ｆ繈宕熼鍌氬箰闂佽绻掗崑娑欐櫠閽樺娲箻椤旂晫鍘遍梺瀹犳〃缁€渚€顢旈鐘亾鐟欏嫭绀冮柨鏇樺灲閵嗕線寮埀顒勫箯閸涙潙绀堥柛娆忣槺缁夊ジ姊婚崒姘偓鎼佸磹閻戣姤鍤勯柛鎾茬閸ㄦ繃銇勯弽顐粶缂佺姳鍗抽幃褰掑炊椤忓秵鈷栧┑鐐叉▕娴滄繈宕戦崟顖涚厽闁规崘娅曢崬澶愭煙閼恒儲绀嬫慨濠冩そ瀹曨偊宕熼鈧粣娑㈡⒑閸濄儱孝婵炴潙鍢查埢搴ㄥ閵堝棗鈧兘鎮楅棃娑欐喐妞ゆ梹娲熷娲偡闁箑娈堕梺绋款儑婵數绮╅悢濂夋建闁逞屽墴瀵鈽夐姀鐘靛幐婵炶揪缍€椤骞忔潏鈺冪＝濞达綀娅ｇ敮娑氱磼鐠囨彃顏€规洜澧楃换婵嬪磻閻ｅ苯鏋庨柣锝傚墲閿涙劖鎷呴崜鍙夘棥闂傚倸鍊烽懗鍓佸垝椤栫偛绀夋俊顖欑秿濞戙垹绀嬫い鎺戝亞濞村嫬顪冮妶鍡樼叆婵℃彃鐗撳顕€宕奸悢铚傛睏闂傚倸鍊搁悧濠勭矙閹邦兘鏌︽い蹇撶墛閳锋垹绱撴担鐧镐緵婵炲牊锚閳规垿顢欓懞銉ュ攭濡炪們鍨哄畝鎼佸极閹邦厼绶炲┑鐘叉搐閺佸綊姊绘担鍛婃儓婵炲眰鍔戝畷鎴︽偄绾拌鲸鏅ｉ梺鍛婄箓鐎氬嘲銆掓繝姘厪闁割偅绻冮ˉ鐘差熆瑜滈崜鐔煎蓟閿濆鏁囩憸宥夊几閵堝棔绻嗛柛娆忣槸婵秹鏌℃担鐟板鐎垫澘瀚埀顒婃€ラ崟顐紲濠电姷鏁搁崑鐘诲箵椤忓棗绶ゅù鐘差儏缁犵儤绻濇繝鍌滃闁告垹濞€閺屾盯骞囬妸锔界彃缂備浇顕уΛ娆撳Φ閸曨垰绠涢柍杞拌兌娴犵厧顪冮妶鍛闁告瑥鍟撮獮鎰節閸屾鏂€闁诲函缍嗛崑鍡涘储娴犲鈷戦梻鍫熺〒缁犲啿鈹戦鐐毈妤犵偛顦靛畷顐﹀Ψ閵忕姳澹曢柣鐔哥懃鐎氼厾浜搁锔界厽闁硅櫣鍋熼悾鍨殽閻愯尙澧﹀┑鈩冩倐婵＄兘顢欓挊澶屾В闂備浇宕垫慨鏉懨洪埡渚囧殨闁规儳顕悵鍫曟煛閸モ晛鏋嶇紒璇叉閺屾洟宕煎┑鍥ㄦ倷闁哥喐鎮傚铏圭矙濞嗘儳鍓辩紓浣割儐閸ㄥ綊宕ｉ崨瀛樷拺闁圭瀛╃粈鈧梺绋匡工閹芥粎鍒掓繝姘兼晬闁绘劕顕崢鍗炩攽閻愭潙鐏﹂柣鐕傚缁辩偤骞嬪婵嗙秺閹虫牠鍩℃担鍙夌€伴梻浣告惈閺堫剟鎯勯姘煎殨闁圭虎鍠栨儫闂侀潧顦崕鍝勵焽婵犳碍鈷掑〒姘ｅ亾闁逞屽墰閸嬫盯鎳熼娑欐珷濠电姵纰嶉悡鏇㈡煏婵炲灝鈧洖鐣甸崱娑欑厱?
    const animationPromise = executeThemeAnimation({ x, y, reducedMotion })
    setTimeout(() => {
      applyTheme(newMode)
    }, config.duration / 2)
    await animationPromise
  }
}

const contentRef = ref<HTMLElement | null>(null)
const maskWrapRef = ref<HTMLElement | null>(null)
const maskPanelRefs = ref<HTMLElement[]>([])
const impactPulseRef = ref<HTMLElement | null>(null)
const inkTopRef = ref<HTMLElement | null>(null)
const inkBottomRef = ref<HTMLElement | null>(null)
const transitionTitleRef = ref<HTMLElement | null>(null)
const transitionTitleText = ref('')
const isModeSwitching = ref(false)
let modeTimeline: gsap.core.Timeline | null = null

const setMaskPanelRef = (el: Element | ComponentPublicInstance | null) => {
  const maybeElement = el instanceof HTMLElement
    ? el
    : (el && '$el' in el && el.$el instanceof HTMLElement ? el.$el : null)

  if (maybeElement) {
    maskPanelRefs.value.push(maybeElement)
  }
}

const maskPanels = Array.from({ length: 12 }, (_, i) => i)

onBeforeUpdate(() => {
  maskPanelRefs.value = []
})


type SidebarRole = 'admin' | 'operator' | 'viewer'

interface SidebarItem {
  to: string
  label: string
  icon: unknown
  roles?: SidebarRole[]
  permissions?: string[]
}

const sidebarMap: Record<ModeKey, SidebarItem[]> = {
  defense: [
    { to: '/defense/dashboard', label: 'Dashboard', icon: Activity },
    { to: '/defense/realtime', label: 'Realtime', icon: Activity },
    { to: '/defense/events', label: 'Threat Ops', icon: ShieldAlert },
    { to: '/defense/ai', label: 'AI Insight', icon: BrainCircuit },
    { to: '/workflow/catalog', label: 'Workflow', icon: Blocks, permissions: ['workflow_view'] },
    { to: '/workflow/runs', label: 'Workflow Runs', icon: Activity, permissions: ['workflow_view'] },
  ],
  probe: [
    { to: '/probe/dashboard', label: 'Dashboard', icon: Activity },
    { to: '/probe/realtime', label: 'Realtime', icon: Radar },
    { to: '/probe/scan', label: 'Scan Ops', icon: ScanSearch },
    { to: '/probe/ai', label: 'AI Insight', icon: BrainCircuit },
  ],
}

const modeDefaultRoute: Record<ModeKey, string> = {
  defense: '/defense/dashboard',
  probe: '/probe/dashboard',
}

const activeModeLabel = computed(() => {
  return activeMode.value === 'defense' ? 'Defense Mode' : 'Probe Mode'
})

const currentSidebarItems = computed(() => {
  const roleValue = role.value === 'admin' || role.value === 'operator' || role.value === 'viewer'
    ? role.value
    : 'viewer'
  return sidebarMap[activeMode.value].filter((item) => {
    if (item.roles && !item.roles.includes(roleValue)) return false
    if (item.permissions && !hasAnyPermission(item.permissions)) return false
    return true
  })
})

const roleText = computed(() => {
  const map: Record<string, string> = { admin: 'Admin', operator: 'Operator', viewer: 'Viewer' }
  return map[role.value] || role.value
})

const roleBadgeVariant = computed(() => {
  return role.value === 'admin' ? ('default' as const) : ('secondary' as const)
})

const unreadNotifications = computed(() => notifications.value.filter((item) => !item.read).length)

// function removed

const resetAnimatedState = () => {
  if (shellRef.value) gsap.set(shellRef.value, { clearProps: 'all' })
  if (sidebarRef.value) gsap.set(sidebarRef.value, { clearProps: 'transform,opacity,filter' })
  if (contentRef.value) gsap.set(contentRef.value, { clearProps: 'all' })
  if (maskWrapRef.value) gsap.set(maskWrapRef.value, { autoAlpha: 0, display: 'none' })
  if (maskPanelRefs.value.length > 0) gsap.set(maskPanelRefs.value, { clearProps: 'all' })
  if (impactPulseRef.value) gsap.set(impactPulseRef.value, { autoAlpha: 0, scale: 0.4, clearProps: 'all' })
  if (inkTopRef.value) gsap.set(inkTopRef.value, { autoAlpha: 0, scaleX: 0, clearProps: 'all' })
  if (inkBottomRef.value) gsap.set(inkBottomRef.value, { autoAlpha: 0, scaleX: 0, clearProps: 'all' })
  if (transitionTitleRef.value) gsap.set(transitionTitleRef.value, { autoAlpha: 0, scale: 1, letterSpacing: '0.5em', clearProps: 'all' })
}

const runModeTransition = async (targetMode: ModeKey) => {
  // 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閹冣挃闁硅櫕鎹囬垾鏃堝礃椤忎礁浜鹃柨婵嗙凹缁ㄥジ鏌熼惂鍝ョМ闁哄矉缍侀、姗€鎮欓幖顓燁棧闂備線娼уΛ娆戞暜閹烘缍栨繝闈涱儐閺呮煡鏌涘☉鍗炲妞ゃ儲鑹鹃埞鎴炲箠闁稿﹥顨嗛幈銊╂倻閽樺锛涢梺缁樺姉閸庛倝宕戠€ｎ喗鐓熸俊顖濆吹濠€浠嬫煃瑜滈崗娑氭濮橆剦鍤曢柟缁㈠枛椤懘鏌嶉埡浣告殲闁绘繃鐗犲缁樼瑹閳ь剟鍩€椤掑倸浠滈柤娲诲灡閺呭爼骞橀鐣屽幍濡炪倖鏌ㄩ崥瀣磻閵夛负浜滈柕蹇娾偓鍐叉懙闂佺硶鏂侀崑鎾愁渻閵堝棗绗掗悗姘煎墴閹锋垿鎮㈤崗鑲╁弳濠电娀娼уΛ娆撳疮閹烘鐓涢柛鎰╁妿婢ф洟鏌ｉ幒鎴犱粵闁靛洤瀚伴獮鎺楀箣濠垫劒鐥梻浣侯焾椤戝懘顢栭崨鏉戠厴闁硅揪闄勯崑鎰版煕濞嗗浚妲归柟顔界懇濮婂搫煤鐠囨彃绠哄銈冨妼閿曨亪骞冮敓鐙€鏁冮柨鏇楀亾闁绘劕锕弻鏇熺節韫囨洜鏆犲銈呯箲閹倸顫忓ú顏勪紶闁告洦鍋呭▓顓㈡⒑缂佹﹩娈旈柨鏇ㄤ簻椤曪綁寮婚妷銉ㄦ憰闂侀潧顧€婵″洭宕㈤崡鐐╂斀闁绘劖娼欓悘銉р偓瑙勬处閸撶喖鎮伴鍢夋棃宕ㄩ鎯у箺闂傚鍋勫ú锕€顫忛悷鎵殾閻忕偟鍋撻崣蹇撯攽閻樻彃顏╅柛鏂款儐缁绘稓鍠婇崣姗€鍋楀Δ鐘靛仜缁夊綊銆佸璺哄窛妞ゆ枮鍕煉婵﹦绮幏鍛存偡闁箑娈濇繝鐢靛仩椤曟粓姊介崟顓犵焿鐎广儱顦介弫鍌炴煕閺囥垺娑ф繛鍫涘妽缁绘繈鎮介棃娴讹絿鐥弶璺ㄐх€规洘鍨垮畷鐔碱敍濞戞艾骞堟繝鐢靛仦閸ㄥ爼鏁冮锕€绀夐柣鏃囨绾剧厧顭跨捄鐚村姛闁糕晪绲鹃幈銊︾節閸愨斂浠㈤悗瑙勬磸閸斿秶鎹㈠┑瀣闁靛ě鍕ㄦ瀳闂傚倸鍊风粈渚€骞夐埄鍐懝婵°倕鎳庣壕濠氭煕閺囥劌澧版い鈺呮敱閵囧嫰骞樼捄鐑樼亖缂備讲妾ч崑鎾绘⒒娴ｅ湱婀介柛銊ㄦ椤洩顦崇紒鍌涘笒椤劑宕奸悢鍝勫箺闂佸湱鍎ゆ繛濠傜暦濠靛洦鍎熼柕濞垮劤椤︻偊姊洪崷顓炲妺闁搞劌缍婂鎶藉幢濞戞瑧鍘撻悷婊勭矒瀹曟粌鈽夊Ο婊愮秮楠炲洭鎮ч崼婵冨亾閻戣姤鍊甸梻鍫熺⊕閹叉悂鏌ｉ敃鈧悧鎾愁潖濞差亜绠归柣鎰絻婵⊙囨⒑缁洖澧查拑閬嶆煕閻斿憡銇濇慨濠傤煼瀹曟帒鈻庨幒鎴濆腐缂傚倷绶￠崳顕€宕规导杈剧稏闊洦姊荤弧鈧┑顔斤供閸撴瑩宕戝澶嬪仭婵犲﹤鍟扮粻鎶芥煕閹烘挸绗ч柟椋庡Т椤斿繘顢欓挊澶婂帪闂備礁鎼ˇ顖炴偋閸曨垰绀夌€光偓閸曨偄鍤戦梺纭呮彧闂勫嫰宕愰崹顐闁绘劘灏欐禒銏ゆ煕閺冣偓绾板秹濡甸崟顖涙櫆閻犲洩灏欐禒鈺呮煛娴ｅ摜澧﹂柡宀嬬磿娴狅妇鎷犻幓鎺戭潛缂傚倷鑳剁€氬繘宕堕妸褍骞堟俊鐐€栭崝褏寰婇崸妤€鐓″璺号堥弨浠嬫煥濞戞ê顏撮柣鎺楃畺濡焦寰勭€ｎ剛鐦堟繝鐢靛Т閸婃悂顢旈锔界厽妞ゆ挾鍠庡ù顕€鏌″畝瀣？濞寸媴绠撻幃娆擃敆閸屻倖效闂佽姘﹂～澶娒哄鍫濆偍鐟滄棃宕洪悙鍝勭闁挎洍鍋撻柣鎰功閹插憡鎯旈…鎴炴櫆闂佽法鍠撴慨鐢稿煕閹烘嚚褰掓晲閸偅缍堥梺绋款儑婵炩偓闁哄本绋掔换婵嬪礃閳哄喚妲梺缁樻尪閸婃牠濡甸崟顖氱闁告鍋熸禒濂告⒑閽樺鏆熼柛鐘崇墵瀵濡搁妷銏☆潔濠碘槅鍨拃锔界閻熸壋鏀介柣鎰皺閻掓儳霉濠婂簼閭€殿喛顕ч埥澶愬閻樻鍟嬫繝寰锋澘鈧劙宕戦幘缁樺€垫慨妯煎帶婢у鈧娲栫紞濠囧蓟閸℃鍚嬮柛鈥崇箲鐎氳棄鈹戦悙鑸靛涧缂傚秮鍋撴繝娈垮枔閸婃繃淇婇幘顔肩妞ゅ繐妫涢敍婊堟⒑闁偛鑻晶顖滅磼濡ゅ啫鏋涢柛鈹惧亾濡炪倖宸婚崑鎾绘煟閿濆洤鍘存鐐叉喘瀵爼宕归閿亾椤撶儐娓婚柕鍫濇閳锋帡鏌涚€ｎ偅灏柍缁樻崌楠炲棜顧佹繛鎾愁煼閺屾洟宕煎┑鍥舵婵犳鍟崨顖滐紲闂佺粯锚閸熷潡鎮橀埡鍐＜妞ゆ棁鍋愭晶銏ゆ煃瑜滈崜銊х礊閸℃稑纾诲ù锝呮贡椤╁弶绻濇繝鍌滃闁绘挻鐟ラ湁闁绘挸娴烽幗鐘崇箾閹冲嘲鍘鹃悷閭︾叆闁告侗鍘哄Σ鎰版⒑閸濆嫯瀚扮紒澶屽厴绡撳〒姘ｅ亾闁哄本鐩獮妯尖偓闈涘閺嗭紕绱撴担铏瑰笡缂佸甯為幑銏犫攽鐎ｎ亞锛滈梺闈涚墕濡稓绮欐担铏圭＝闁稿本鑹鹃埀顒傚厴閹偤鏁冩担瑙勫櫡婵犵數濮甸鏍垂闁秴绠伴柟鎯版閽冪喖鏌ㄥ┑鍡╂Ц缂佺媴缍侀弻锝堢疀閺冣偓閵囩喎霉濠婂嫮鐭掗柛鈹垮灲楠炴﹢寮甸崹顐㈠缂傚倷鐒︾粙鎴︻敄閸℃瑢鍋撻棃娑氱劯婵﹥妞藉Λ鍐ㄢ槈濮橆剦鏆┑掳鍊楁慨鎾箟閿涘嫮鐭夌€广儱鎳夐弨浠嬫煕閵夈垺娅囨い鏃€娲熷娲嚃閳圭偓瀚涢梺鍛婃尰閻熲晛顕ｉ崨濠冨劅闁靛濡囬崢浠嬫⒑閹稿海绠撴繛璇х畵閹偤宕稿Δ浣哄帾闂佹悶鍎崝灞炬叏瀹ュ棭娈介柣鎰綑濞搭喗顨ラ悙杈捐€跨€殿喖鐖奸獮瀣攽閸♀晜缍囬梻鍌氬€搁崐鎼佸磹妞嬪孩顐芥慨姗嗗墻閻掍粙鏌ゆ慨鎰偓鎰板磻閹剧粯顥堟繛鎴炴皑閸旑垶鎮楃憴鍕８闁搞劍妞芥俊鍫曟晲婢跺﹦顦ㄩ梺瀹犳〃濡炴帞鑺遍悽鍛娾拻濞达絿鐡斿鎰版煕鎼淬垹鈻曟い銏″哺椤㈡﹢鎮╅幓鎹岸姊洪柅鐐茶嫰婢у瓨鎱ㄦ繝鍐┿仢婵☆偄鍟埥澶愬閵忕姵銇濈紓鍌氬€峰ù鍥ь嚕閹捐泛鍨濇繛鍡樻尭缁犳牠鏌ㄩ悢鍝勑㈢紒鐘崇洴閺岋絽螖閳ь剟鎮ц箛娑樺偍闂侇剙绉甸埛鎴︽煕濠靛棗顏╅柡鍡欏仱閺岀喖骞栨担铏规毇闂佽鍣ｇ粻鏍箖閻ｅ苯鏋堟俊顖濇〃婢规洖鈹戦悙鑼闁诲繑绻傞埢宥咁潨閳ь剟寮诲☉姘ｅ亾閿濆簼鎮嶇€规悶鍎甸弻锝夋晲閸パ冨箣濡ょ姷鍋炵敮鎺曠亙婵炶揪绲跨涵鍫曞磻閹剧粯鍊婚柤鎭掑劚閳ь剛鏁婚弻锝夊閳藉棗鏅遍梺缁樺笧閸嬫捇銆冮妷鈺傚€烽柤纰卞墮椤も偓濠电儑绲藉ú銈夋晝椤忓牆绠栨繛鍡樻惄閺佸倿鏌涢弴妯哄濞存粓绠栭弻鈥愁吋鎼粹€崇缂備讲鍋撳璺烘湰閸犳劙鐓崶銊︽儎闁搞倖顨呴埞鎴︽偐閸欏鎮欓梻浣斤骏閸婃牗绌辨繝鍥ч柛灞剧煯婢规洟姊绘担铏瑰笡闁规瓕宕甸幑銏ゅ醇閵夈儴鎽曢梺缁樻⒒閸樠呯矆閸垺鍠愰煫鍥ㄦ礃閺嗘粍绻涢幋娆忕仾闁绘挾鍠栭弻鐔煎箚瑜忛幗鐘电磼閳ь剛鈧綆鍠楅悡娆愩亜閺冨倻鎽傛繛鍫熺矒閺屸剝鎷呴悷鏉款潔闂佽鍨卞Λ鍐垂妤ｅ啯鍤戞い鎺嗗亾闁搞値鍓熷缁樻媴缁涘娈紓浣虹帛閸旀骞戦姀銈呯闁绘劗鏁歌ぐ楣冩⒑缁洖澧茬紒瀣灴閹偤宕归鐘辩盎闂佺懓鎼Λ妤佺妤ｅ啯鈷戦悹鍥皺缁犳煡鏌よぐ鎺旂暫闁炽儻绠撳畷褰掝敊閵壯冩灁濞存粍鎮傚鍊燁槺濠㈣娲栭埞鎴︻敊閺傘倓绶甸梺绋款儏鐎氼剟鎮鹃悽绋垮耿婵炴垶鐟ч崢钘夆攽閻愭潙鐏ョ€规洦鍓欓埢宥咁吋閸ワ絽浜鹃悷娆忓缁€鈧梺缁樼墪閵堟悂濡存担鑲濇梹鎷呴崫銉х嵁闂佽鍑界紞鍡涘磻閸涘瓨鍋熸繝闈涱儐閳锋垿鏌ゆ慨鎰偓鏇㈠几閹寸姷纾兼い鏃囧亹閻掓悂鏌＄仦鏂よ含闁轰焦鍔欏畷濂告偆閸屾粎锛濋梻鍌氬€搁崐椋庣矆娴ｅ湱鐝跺┑鐘叉搐绾惧鏌涢埄鍐槈缂佹劖顨堥埀顒€绠嶉崕鍗灻洪敃鈧悾鐑藉蓟閵夛妇鍘遍梺鏂ユ櫅閸熶即鍩婇弴銏＄厽闁规崘娉涢弸娑㈡煛瀹€鈧崰鏍ь嚕閸洖鍨傛い鏃囨閳ь剙娴风槐鎾存媴闂堟稑顬堝銈庡幘閸忔ê顕ｇ拠宸悑闁割偒鍋呴鍥⒒娴ｄ警鐒剧紒缁樺灴閹兘鍩℃担鐑樻闂佸綊鍋婇崗姗€寮ㄦ禒瀣厱闁斥晛鍟伴幊鍕箾閸儳鐣烘慨濠呮濞戠敻宕ㄩ鍏奸敪缂傚倷鑳舵慨鐢稿垂閸︻厼鍨濆┑鐘崇閹偞銇勯幇鍓佺？缂佺姵宀稿娲濞戞艾顣洪梺绋匡工閹诧紕绮嬪澶婄鐟滃繒澹曢挊澹濆綊鏁愰崶銊ユ畬婵犳鍠栭悧濠囧Φ閸曨垰惟闁靛瀵屽Λ锕€螖閻橀潧浠滈柣妤佹尰娣囧﹪骞栨担鑲濄劑骞栨潏鍓у埌闁哄鍨归埀顒€鐏氬妯尖偓姘煎枤閸掓帒鈻庨幘宕囶唶闁硅偐琛ラ埀顒€鍟块ˉ鎺楁⒒閸屾艾鈧悂宕愰悜鑺ュ€块柨鏇楀亾妞ゎ亜鍟村畷绋课旈埀顒勫磼閵娾晜鐓熼柟鎯у暱椤斿倹绻涢幋鐐冩岸寮ㄦ禒瀣€甸柨婵嗙凹濞寸兘鏌熼懞銉︾闁宠鍨块幃娆撳级閹寸姳鎴烽梻浣规偠閸斿瞼绱炴繝鍌滄殾闁跨喓濮寸粻顕€鏌ら幁鎺戝姢闁告﹩浜濈换婵嬫偨闂堟稐绮堕梺璇茬箲缁诲牆鐣峰┑瀣ч柛姘ュ€曠紞濠囧箖椤忓牆鐒垫い鎺戝閻鏌涢幇鐢靛帥婵炲吋鐗犻弻褑绠涢幘纾嬬缂佺偓鍎抽崥瀣┍婵犲浂鏁嶆繝鍨姇濞堫參姊婚崒姘兼Ц缂佸鎸抽崺鐐哄箣閿旇棄鈧兘鎮规ウ鎸庮仩婵絻鍨藉娲传閵夈儛锝夋煟濡や焦绀嬫い銏″哺閺佹劙宕卞▎鎴犳婵犳鍠楅敃鈺呭礈濞戞瑥顕遍悗锝庡枟閸婄敻鎮峰▎蹇擃仾缂佲偓閳ь剙鈹戦悙棰濆殝缂佺姵鍨块崺銏ゅ箻缂佹ê浜楅柟鍏兼儗閸犳鈧潧鐭傚娲濞戞艾顣哄┑鈽嗗亝閻熲晠宕哄☉銏犵婵°倓鑳堕崢鍗炩攽閳藉棗鐏ｅ┑顔芥綑闇夐柛宀€鍋涢弸渚€鏌涘畝鈧崑鐐烘偂閸愵喗鐓曟繝闈涙椤忊晠鏌嶈閸撴繂鐣烽悽闈涘灊缂備焦菧閸嬪懘鏌涢幇銊︽珖闁告ê宕埞鎴︽倷閺夋垹浠撮悗瑙勬处閸撴氨绮嬪鍜佺叆闁割偆鍠撻崢鎾绘偡濠婂嫮鐭掔€规洘绮岄～婵囨綇閵娿儱绨ラ梻浣稿閸嬪懐鎹㈠澶婂惞?settings/integrations/audit 缂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閻愵剙鍔ょ紓宥咃躬瀵鎮㈤崗灏栨嫽闁诲酣娼ф竟濠偽ｉ鍓х＜闁绘劦鍓欓崝銈囩磽瀹ュ拑韬€殿喖顭烽弫鎰緞婵犲嫷鍚呴梻浣瑰缁诲倿骞夊☉銏犵缂備焦顭囬崢杈ㄧ節閻㈤潧孝闁稿﹤缍婂畷鎴﹀Ψ閳哄倻鍘搁柣蹇曞仩椤曆勬叏閸屾壕鍋撳▓鍨珮闁告挾鍠庨悾鐤亹閹烘繃鏅╅柣鐔哥懃鐎氼剟鎯侀柆宥嗏拻闁稿本鐟ч崝宥嗕繆閻愬弶鍋ョ€规洏鍨虹粋鎺斺偓锝庡亜娴狀參姊洪崘鍙夋儓闁瑰啿閰ｉ幏鎴︽偄閸忚偐鍘介梺鍝勫€藉▔鏇炩枔闁秵鐓涢悗锝庝邯閸欏嫭鎱ㄦ繝浣虹煓鐎规洖鐖奸、妤佸緞鐎ｎ偅鐝ㄩ梺鑽ゅ枑缁瞼绮旈崼鏇炵煑闁告侗鍙庡〒濠氭煏閸繃顥為柟顖氬缁绘盯鎮℃惔銏犱淮闂佺硶鏂侀崑鎾愁渻閵堝棗鐏辨繛澶嬫礋钘濋柨鏂款潟娴滄粍銇勯幇鍓佹偧缂佺姵锕㈤弻鐔兼偡閺夋浼冮梺鍦帶缂嶅﹪骞冮悜钘夌骇闁哥喎鍟ú鏍煘閹达附鏅柛鏇ㄥ亗閺夘參姊虹粙鍖℃敾闁绘绮撳顐︻敋閳ь剟鐛幒妤€妫橀柛婵嗗婢规洖鈹戦绛嬬劷闁告鍕珷闁规鍠氱壕鍏笺亜閺冨倵鎷￠柣鎾炽偢閺岀喖顢欑憴鍕彅闂佷紮绲块崗妯虹暦閸洖鐓涘┑鐘插€瑰▍妤呮⒒閸屾艾鈧兘鎳楅崜浣瑰厹闁割偅娲栫粈鍫熺節闂堟冻鏀婚柟鍐茬焸濮婅櫣鎷犻懠顒傤唶濠电偛鐡ㄥ畝绋跨暦閵忋倕绀堢憸搴綖閺囥垺鐓欓柣鎴烇供濞堟洟鏌涚€ｎ偄鐏撮柡灞剧☉閳藉宕￠悙鍏稿寲闁荤偞鐔粻鎾愁潖缂佹ɑ濯撮柛娑橈攻閸庢捇鏌ｉ悙鏉戝毈闁稿锕ら悾宄扳攽鐎ｎ亞顓哄┑鐘茬仛閸旀洖鈻撻妸鈺傗拺闁告繂瀚峰Σ褰掓煕閵堝繒鐣电€殿噮鍣ｅ畷鐓庘攽閸繂袝濠碉紕鍋戦崐鏍暜婵犲洦鍤勯柛顐ｆ磸閳ь剙鎳樺濠氬Ψ閿旀儳骞堥梻浣告贡閸嬫捇銆冮崨鏉戠疇闁规壆澧楅弲顒佺節闂堟稒宸濈紒鐘荤畺瀵爼宕煎┑鍡忔寖闂佸憡甯婇崡鎶藉蓟閻斿搫鏋堥柛妤冨仒缁ㄥジ姊虹紒姗嗘當闂佸府绲介～蹇曠磼濡顎撻柣鐔哥懃鐎氼剚绂掗埡鍛拺闁告稑锕ラ悡銉╂煟椤掑啫浜规俊鍙夊姍閹瑧鈧潧鎽滈惁鍫ユ⒑閹肩偛鍔楅柡鍛〒缁﹪鏁傞悾宀€鐦堥梺闈涢獜缁蹭粙鎮￠幇鐗堢厱闁哄啠鍋撴繛鍙夌矌閸掓帗绻濆顓炰画闂佺懓鍟块敃銈囩礊婵犲洤鏋侀柟鐗堟緲瀹告繃銇勯弮鍥棄闁哄鍨垮缁樻媴鐟欏嫨浠ч梺绋款儏鐎氼噣鍩€椤掍胶顣叉繝銏★耿閿濈偠绠涢幘浣规そ椤㈡棃宕熼褎肖闂傚倷绀佸﹢杈╁垝椤栨粍鏆滃┑鐘插婵啿鈹戦崒姘暈闁抽攱鍨块幃褰掑炊閿濆倸浜剧€规洖娲ｉ崫妤呮⒒娴ｇ懓顕滄繛璇ч檮缁傚秴鈹戦崶鈹炬敵婵犵數濮村ú锕傚磹婵犳碍鐓㈡俊顖滃皑缁辨岸鏌曟繝蹇氱濞存粍绮撻弻锟犲礃閿濆懍澹曢梻浣侯焾鐎涒晜绻涙繝鍌ゅ殨妞ゆ劧绠戠粻鐟懊归敐鍛辅闁归绮换娑欐綇閸撗勫仹濡炪値鍘奸悧鎾荤嵁閸愵喖绠ｉ柨鏃傛櫕閸橀潧顪冮妶鍡樷拻闁告鍥х劦妞ゆ帊鐒﹂崐鎰版煃閵夘垳鐣电€规洖鐖奸、鏂款吋閸犻偊浜缁樼瑹閳ь剟鍩€椤掍胶銆掗柍瑙勫浮閺屾盯寮埀顒勫垂閻㈠憡鍋╅梺鍨儑闂勫嫰鏌涘☉姗堝伐濞存粍绮庣槐鎾诲磼濮樺崬鈪辨繝娈垮枤閸忔﹢骞嗛崟顒佸劅闁靛鑵归幏缁樼箾閹炬潙鐒归柛瀣尰缁绘稒鎷呴崘鍙夌〗闁搞儺鍓﹂弫鍥煏韫囨洖啸闁挎稓鍠栧娲箚瑜庣粋瀣煕鐎ｎ亝鍣归柍璇茬Ч閹晛鐣烽崶鈺婂晭闂備胶鎳撻悺銊╂偡閵夆晜鍊舵い蹇撶墛閻撶喖鏌熼幆褏锛嶇紒鐘差煼閺岋紕浠﹂崜褎鍒涙繝纰夌磿閸忔﹢鐛€ｎ亖鏀介柛鈩冾焽娴滄儳鈹戦悙宸殶闁告鍥х柈妞ゆ劧鑵归埀顒佹瀹曟﹢顢欓崲澹洦鐓曢柟鎵虫櫅婵″灝霉閻樺啿鍔ら柍瑙勫灴閹瑧鎹勯搹瑙勵嚄闂備礁鎽滄慨鐢告偋閻樺厖绻嗛悗娑欘焽閻熷綊鏌嶈閸撴瑩顢氶敐澶婄妞ゆ梻鈷堝濠囨⒑缂佹鎲块柛瀣尰缁绘盯鎮℃惔顖濆惈濠殿喖锕ュ浠嬬嵁閹邦厽鍎熼柨婵嗗€归～宥夋⒑鐠囨彃顒㈤柛鎴ｎ潐缁傚秴鈹戦崼銏犲触闂佺粯姊婚崢褔宕￠幎鑺ョ厽婵☆垰鍚嬮弳鈺呮煥濞戞瑧绠炴慨濠呮缁瑩骞愭惔銏″闂備胶鍘х紞濠勭不閺嶎厼鏄ラ柍褜鍓氶妵鍕箳閹存繍浼屽┑鈽嗗亝閸ㄥ潡寮婚悢椋庢殝闂侇叏绠戦崜鍫曟倵濞堝灝鏋涙い顓㈡敱娣囧﹪鎮滈挊澹┿劎鎲稿┑鍫燁潟闂侇剙绉甸埛鎺懨归敐鍥у妺闁搞倐鍋撳┑鐘媰閸涱喗鐝梺鍛婂笚鐢繝銆佸☉銏″€烽柡澶嬪灣缁ㄧ敻姊绘担鍛婃儓婵炲眰鍨藉畷鐟懊洪鍛簵闂佸憡鍔﹂崰妤呮偂閸愵喖绾ч柣鎰綑椤ュ銇勯敂鑲╃暤闁哄矉绻濆畷鍗炩枎韫囨梻浜梻浣告惈閼活垳绮旇ぐ鎺嬧偓浣糕槈濡攱顫嶅┑鐐叉閸╁牆危瑜版帗鈷?
  // 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤缂嶅﹪寮婚悢鍏尖拻閻庨潧澹婂Σ顔剧磼閹冣挃闁硅櫕鎹囬垾鏃堝礃椤忎礁浜鹃柨婵嗙凹缁ㄥジ鏌熼惂鍝ョМ闁哄矉缍侀、姗€鎮欓幖顓燁棧闂備線娼уΛ娆戞暜閹烘缍栨繝闈涱儐閺呮煡鏌涘☉鍗炲妞ゃ儲鑹鹃埞鎴炲箠闁稿﹥顨嗛幈銊╂倻閽樺锛涘┑鐐村灍閹崇偤宕堕浣镐缓缂備礁顑嗙€笛囨倵椤掑嫭鍊垫鐐茬仢閸旀碍銇勯敂璇茬仯缂侇喖鐗忛埀顒婄秵閸嬩焦绂嶅鍫熺厵闁告繂瀚倴闂佸憡鏌ㄧ粔鐢稿Φ閸曨垰妫橀柟绋块閺嬬姴鈹戦纭峰姛缂侇噮鍨堕獮蹇涘川閺夋垵绐涙繝鐢靛Т閹虫劙銆侀崨瀛樷拻濞达絼璀﹂悞鍓х磼閵婏附銇濈€规洘鍔曢埞鎴﹀幢濞嗘劖顔曢梻鍌氬€搁悧濠冪瑹濡も偓椤洭鍩￠崒妯圭盎闂佺懓顕慨瀛樼閿旀垝绻嗛柣鎰閻瑩鏌曢崱鏇犵獢鐎殿噮鍣ｅ畷鐓庘攽閸℃瑧宕哄┑锛勫亼閸婃牕顫忔繝姘柧妞ゆ劑鍎禍褰掓煕閵夘喖澧柍閿嬪浮閺屾稓浠﹂崜褎鍣紓浣瑰姈濡啴寮诲鍫闂佸憡鎸婚惄顖氱暦閹存績妲堥柕蹇娾偓铏吅婵＄偑鍊栭悧妤冪矙閹烘垟鏋嶉柣妯肩帛閻撴瑧绱撴担闈涚仼闁哄鍠栭弻锝夊箻鐎靛憡鍣梺闈涙搐鐎氭澘顕ｉ弶鎳虫棃鍩€椤掍胶顩查柛鎾楀懐锛濇繛杈剧到閹碱偅鐗庨梻浣虹帛椤ㄥ牊绻涢埀顒勬煟濞戝崬娅嶇€规洘锕㈤垾锕傚箣閻樻彃姹查梻鍌欑婢瑰﹪宕戦崱娑樼獥閹兼番鍔嶉崕宀勬煕閺囥劌澧扮紒鈾€鍋撻梻渚€娼ф蹇曞緤閸撗勫厹濡わ絽鍟崐鍨箾閹寸偛绗氭繛鍛攻椤ㄣ儵鎮欏顔叫ч柣搴濈祷閸嬫劙鍩€椤掍胶鈯曢懣銈夋煙妞嬪海甯涚紒缁樼洴楠炴﹢寮堕幋鐘插Р闂備胶顭堥鍡涘箰閼姐倖宕叉繛鎴炵懄婵挳鏌涢幇顒€绾х痪顓濈矙閺屾盯濡烽鐓庘拻闂佽桨绀佸ú顓㈠蓟閺囷紕鐤€闁哄洨鍊妷鈺傜叆婵炴垶鑹鹃弸娑欐叏婵犲懏顏犻柟鍙夋尦瀹曠喖顢曢姀鐘橈箑鈹戦悩鎰佸晱闁哥姵鎹囧畷鎰攽閸℃瑦娈鹃梺鍝勬储閸ㄥ湱绮婚懡銈囩＝濞达綀顕栭悞浠嬫煕濮椻偓娴滆泛顫忓ú顏勪紶闁告洦鍓欓崑宥夋⒑閸涘﹥鐓ラ柣顓炲€块獮鍐潨閳ь剟寮幘缁樺亹鐎规洖娲ょ敮妤呮⒒閸屾瑧顦﹂柣蹇旂箞椤㈡牠宕ㄧ€涙ê鈧爼鏌熺紒銏犳灍闁绘挻鐩幃姗€鎮欓幓鎺嗘寖濠电偞褰冮悺銊┿€冮妷鈺傚€烽弶鍫熷礃閳ь剝娉曢埀顒侇問閸犳牠鎮ユ總鍝ュ祦閻庯綆鍠楅崑鎰版煟閹邦喗鍤€濞寸媭鍘奸埞鎴︽偐閸偅姣勯梺绋款儐閻╊垶骞冨ú顏勎╃憸宥夊垂濠靛牃鍋撻獮鍨姎婵炶绠戦悾鐑藉蓟閵夛妇鍘遍梺瑙勬緲閸氣偓缂併劏鍋愰埀顒冾潐濞叉牕顕ｉ崜浣瑰床婵炴垯鍨圭粻锝嗙箾閸℃绠冲ù鐘层偢濮婂搫煤鐠囨彃绠哄銈冨妼閹虫﹢鍨鹃敂鐐磯闁靛绠戠壕顖涗繆閵堝繒鐣遍柣蹇旂箞椤㈡棃顢橀姀鈾€鎷洪梺鍛婂姈瑜板啫危婵犳碍鐓熸い鎾跺仜閳ь剙娼￠悰顕€宕橀妸搴㈡瀹曟﹢鍩℃担鍦偓顓㈡⒒娴ｅ憡鍟炴繛璇х畵瀹曟粌鈽夐姀鈩冩珫濠殿喗銇涢崑鎾存叏婵犲啯銇濇鐐寸墵閹瑩骞撻幒婵堚偓杈╃磽閸屾瑧璐伴柛鐘愁殜閹兘鍩￠崨顓犵暫婵炴潙鍚嬮幆宀勫极婵犲嫮妫柟宄扮焸閸濊櫣鈧偣鍊栧钘夘潖濞差亝鐒婚柣鎰蔼鐎氭澘顭胯閹告娊寮婚弴銏犲耿闁哄洨濯Σ顕€姊虹€圭媭鍤欓梺甯秮閻涱喖螣閾忚娈鹃梺鎼炲劗閺呮粌袙鎼淬劍鈷戦柤濮愬€曢弸鎴犵磼椤旇偐鐏辩紒顔芥⒒閹瑰嫭绗熼姘唫濠电姷鏁告慨鎾疮娴煎瓨鈷旈柛鏇ㄥ灡閻撴洘绻涢幋鐐╂闁割偁鍎辩粻顖滅磽娴ｈ鐒界紒鐘荤畺瀵爼宕煎┑鍡忔寖缂備礁顦介崜姘跺Φ閸曨垼鏁冮柕蹇婃櫆閳诲牓鎮楃憴鍕闁搞劌娼￠獮鍐煛閸愵亞锛滃┑鈽嗗灣閸樠囩嵁閸儲鈷戦柣鐔告緲閹垿鏌ｉ敐搴濋偗鐎规洝顫夌换婵嗩潩椤撶偛澹掗梻浣告贡閸庛倝寮婚敓鐘茬；闁规崘鍩栭崰鍡涙煕閺囥劌澧版い锔诲弮濮婃椽宕妷銉愶綁鏌ｅΔ鍐ㄢ枅濠碘€崇摠缁楃喖鍩€椤掆偓椤曪綁骞橀纰辨綂闂佹枼鏅涢崯顖炴偟閹惰姤鈷掑ù锝堫潐閸嬬娀鏌涙惔顔肩仸鐎规洘绻傞鍏煎緞鐎ｎ亜澧鹃梻浣烘嚀婢х晫鍒掗鐐茬厱闁圭儤顨嗛悡鏇㈡倶閻愭潙绀冨瑙勶耿閺屽秷顧侀柛鎾村哺楠炲啴宕掑杈ㄦ闂佸綊鍋婇崣搴∥ｈぐ鎺戠婵烇綆鍓欓悞娲煕鐎ｃ劌濡奸柍瑙勫灴椤㈡瑩寮妶鍕繑闂備礁鎲￠幖顐ょ不閹捐绠栭柣鎰劋閸嬧晠鎮橀悙鏉戝姢闁哄鍨块幃妤呯嵁閸喖濮庨梺缁橆殔缁绘垹绮嬪鍡樼秶闁靛ě鍛闁诲骸鍚€閸楁娊寮ㄩ崡鐑嗙唵婵せ鍋撻柛鈹惧亾濡炪倖甯婇悞锔剧矆鐎ｎ兘鍋撶憴鍕闁搞劌鐖奸妴浣糕槈濮楀棙鍍甸柡澶婄墑閸斿秹顢欓弴銏♀拻濞达絽鎲￠幆鍫ユ偠濮樼厧浜扮€规洘娲熷濠氬Ψ閿曗偓娴滄鈹戦悙鍙夘棡闁圭顭烽幃锟犳偄閸忚偐鍘甸柣搴ｆ暩椤牓宕滈崘灞傗偓鎺戭潩椤撶姭濮囩紓浣虹帛閻╊垰鐣锋總鍛婂亜缂侇垱娲樼€氱晫绱撻崒娆愮グ濡炴潙鎽滈弫顕€鏁撻悩鑼暫闂佸啿鎼幊蹇浰夐崼鐔虹闁瑰鍋熼幊鍛瑰搴濋偗婵﹦绮幏鍛村川婵犲啫鍓甸梻浣规た閸撴瑩濡剁粙璺ㄦ殾濞村吋娼欑粻濠氭煠閸涘鍟忔繛鑲╁枛濮婃椽宕烽鐐插濡炪們鍔岄幊姗€鏁愰悙鍝勫窛閻庢稒顭囬崢钘夆攽閳藉棗鐏ユ繛鍜冪秮閺佸秴顓奸崥銈囨嚀椤劑宕橀鍕幗婵犳鍠栭敃锔惧垝椤栫偛绠柛娑欐綑瀹告繂鈹戦悩鎻掓殭闁告挾鏁诲缁樻媴閻戞ê娈岄梺鍝ュ枙濞夋洟骞戦姀銈呯婵°倐鍋撶紒鐘崇叀閺屾洝绠涚€ｎ亖鍋撻弴銏＄厑闁搞儺鍓氶悡蹇擃熆鐠鸿櫣澧曢柛鏂诲劦閺岀喖鎳為妷锔绢槹闂佽鍠楅〃濠囨偘椤曗偓瀹曞綊顢欓悡搴經闂傚倷鑳剁划顖炪€冮崱娆忓灊鐎光偓閸曘劉鍋撻弽銊х瘈闁搞儺鐏涢埡鍛厓闁告繂瀚埀顒傛暬楠炲繐煤椤忓應鎷洪梺鍛婄☉閿曪箓鍩ユ径鎰叆闁哄洦锚閸斻倕霉濠婂嫭鍊愭鐐茬Ч椤㈡瑩宕滆缁辨煡姊洪懡銈呅㈡繛娴嬫櫇娴滅鈻庨幇顓熺彿濠电偞鍨堕妴鎺撴償閵娿儳鍊為悷婊勭箞閻擃剟顢楅崟顒傚幍濡炪倖姊婚崑鎾斥枍閺囩姷纾兼い鏃傛櫕閹冲懘鏌熼悷鏉款伃濠碘剝鐡曢ˇ铏節閵忊€崇伌婵﹤顭峰畷鎺戔枎閹搭厽袦闂備礁婀遍埛鍫ュ磻婵犲懏顥ら梻浣告啞閸旀牜绮婇幘顔煎嚑闁哄稁鍘介悡娑㈡煕閵夛絽鍔氶柣蹇ｄ邯閺岋繝宕担绋款潽缂備胶绮换鍐崲濠靛纾兼慨姗嗗幗閻や線姊绘担濮愨偓鈧柛瀣尭闇夐柣妯烘▕閸庢劙鏌ｉ幘璺烘瀾濞ｅ洤锕、娑樷攽閸℃鍎梻浣烘嚀閸熷潡宕幘顔肩畺婵°倐鍋撴い顐ｇ箞閹剝鎯旈埦鈧幏顐︽煟鎼淬値娼愭繛鍙夘焽閹广垽宕奸悢鍓佺畾闂佸壊鍋呭ú鏍喆閿曞倹鐓忛柛顐ｇ箖婢跺嫰鏌涢妶鍌氫壕濠碉紕鍋戦崐銈夊储瑜版帒绀夐柟瀛樼箘閺嗭箑鈹戦崒婊庣劸妞ゎ偄鎳橀弻鏇＄疀婵犲倸鈷夐梺浼欓檮鐢€愁潖婵犳艾纾兼繛鍡樺焾濡差噣姊洪崷顓涙嫛闁稿锕獮鍡欎沪閹呯獮閻庡厜鍋撻柍褜鍓涚划鍫熺節閸屾ǚ鍋撻幒鎴僵闁挎繂鎳嶆竟鏇熶繆閵堝洤啸闁稿鐩畷顖溾偓娑櫳戦崣蹇涙煃瑜滈崜鐔煎蓟閺囥垹閱囨繝闈涙搐濞呫垻绱撴担绋胯埞闁绘牜鍘ч～蹇撁洪鍕獩婵犵數濮撮崯浼此囬妷鈺傗拺閻犲洩灏欑粻鏌ユ煠鐟欏嫬绀冩い锝囧亾缁绘繈濮€閿濆棛銆愬銈嗗灥濞层劌顕ｈ閸┾偓妞ゆ帒瀚埛鎴炴叏閻熺増鎼愰柣蹇撳级缁绘稒鎷呴崘鍙夘棏闁告瑦鎸冲濠氬磼濞嗘帒鍘″銈庡幖閻楁捇銆侀弽顓炲耿婵炴垶顭囬鍥⒑瑜版帗锛熼柣鎺炲缁骞掑Δ浣叉嫽婵炶揪缍€濞咃絿鏁☉銏＄厵闁告縿鍎洪悞楣冩婢舵劖鐓熼柟杈剧稻椤ュ绱掗悩铏仢闁哄矉绲借灒闁兼祴鏅涚粭锟犳⒑缂佹ɑ灏甸柛鐘崇墵瀵鎮㈤悡搴ｇ暰閻熸粍绮撳畷鐢告偄閸濄儳顔曢梺鍛婄懃椤︽壆浜搁敃鍌涚厸鐎光偓鐎ｎ剛锛熸繛瀵稿缁犳挸鐣峰鍡╂Ъ闂佸憡甯楅惄顖氼潖閾忕懓瀵查柡鍥╁枑濠㈡捇姊虹粙鍧楀弰婵炰匠鍥ㄥ仼闁绘垼妫勭涵鈧梺缁樺姇缁夐潧螞閸愵喖鏄ラ柍褜鍓氶妵鍕箳閹存績鍋撶紒妯尖枖鐎广儱顦伴悡鐘测攽椤旇棄濮囬柍褜鍓氶〃鍫熺珶閺囥垺瀵犲瑙勭箓缂嶅﹪寮幇鏉垮窛妞ゆ挆鍕垫濠电姷顣藉Σ鍛村垂娴煎瓨鍋嬮柟鎹愵嚙閽冪喐绻涢幋娆忕仾闁稿鍔欓弻娑㈠箛椤撶偟绁烽梺鍦櫕閺佽顫忛搹鐟板闁哄洨鍠愬鎺楁⒑缁嬫鍎愰柟鍛婃倐閳ユ棃宕橀鍢壯囨煕閳╁喚娈橀柣鐔村姂濮婃椽宕妷銉愶綁鏌よぐ鎺旂暫闁炽儻绠撳畷鍫曨敆閳ь剛绮诲☉娆嶄簻闁规崘娉涘暩濡炪倖姊瑰ú鐔奉潖濞差亜宸濆┑鐘插閸Ｑ冾渻閵堝繒绱扮紒顔界懇楠炲啴鎮欑€靛壊娴勯柣搴秵閸嬪棝宕㈤棃娴虫棃鎮╅棃娑楃捕闂佽绻戠换鍫ュ箖濮椻偓閹崇娀顢栭挊澶夊闁荤喐鐟ョ€氼厾绮堥埀顒勬⒑闂堟稓澧涢柟顔煎€块悰顕€宕橀纰辨綂闂侀潧鐗嗛幊鎰八囬鐔虹閺夊牆澧界粔顒佺箾閸滃啰绉€殿喗濞婂鑸垫償閹惧瓨鏉搁梻浣虹帛钃遍柛鎾村哺瀹曨垵绠涘☉娆戝幈闂佺粯蓱閸撴艾鈻撳鈧弻鐔肩嵁閸喚浼堥悗瑙勬礃鐢繝骞冨▎鎾崇骇闁瑰瓨绻傞ˉ妤呮⒒閸屾瑧顦﹀鐟帮躬瀹曟垿宕ㄩ弶鎴犵暰婵犵數濮村ú锕傚疾閺屻儲鐓曢柍鈺佸暟閹冲洦淇婄紒銏犳珝婵﹥妞藉畷銊︾節閸曘劍顫嶉梺鑲╂嚀閻倿寮婚悢鍏肩叆閻庯綆鍋佹禒銏犫攽椤旂》鏀绘俊鐐舵閻ｇ兘濡搁敂鍓х槇闂佸憡娲﹂崢楣冨汲閵堝鈷戦悹鍥ㄥ絻椤掋垽鏌涢幋婵堢Ш鐎规洩缍佸畷姗€顢橀悤鍌滅＝婵犵數濮烽弫鎼佸磻濞戞娑樷枎閹惧磭顔囨繝鐢靛У绾板秹宕戦崒鐐寸厸闁搞儮鏅涢弸宥囩磼鐠囧弶顥㈤柡灞炬礋瀹曠厧鈹戦崱鈺€绱戞俊鐐€х拋锝囩不閹捐钃熺€广儱娲ㄧ壕鍏间繆椤栨繂鍚规い锔诲弮濮婃椽鏌呴悙鑼跺濠⒀屽灡閵囧嫰寮埀顒勬偋閻樿尙鏆﹀ù鍏兼綑閸愨偓濡炪倖鎸荤粙鍫ュ磻閹剧粯鏅濋柛灞剧〒閸欏棝鏌ｆ惔顖滃矝闁哄懏绻勭划璇差潩閼哥鎷洪悷婊呭鐢鏁嶉悢铏圭＜闁逞屽墯閹峰懘宕ㄦ繝鍐╊唶闂傚倸鍊搁崐椋庢濮橆剦鐒界憸蹇涘箲閵忋倕骞㈡俊鐑嗘緛缂嶄礁鐣烽妸鈺婃晣鐟滃繘宕濋悜鑺モ拺闁告繂瀚弳濠囨煕鐎ｎ偅灏电紒杈ㄥ笧缁辨帒螣閼测晝鏆梻浣告憸婵挳鏁冮妶鍫航婵犵數鍋犵亸娆戝垝椤栨粎绀婂鑸靛姈閳锋帒霉閿濆牜娼愰柛瀣█閺屾盯寮▎鎯у壎閻庤娲╃换婵嬬嵁鎼淬劍瀵犲璺虹灱閺嗩偅绻濈喊妯活潑闁搞劎鏁绘俊鎾焵椤掑嫭鐓涢柍褜鍓氱粋鎺斺偓锝庡亜閳ь剛鏁婚弻銊モ攽閸℃ê娅ф繛瀵稿У閻╊垶寮婚敓鐘插窛妞ゆ柨澧介悡鈧俊鐐€ゆ禍婊堝疮鐎涙ü绻嗛柛顐ｆ礀楠炪垺淇婇婊冨妺婵炲牜鍋婂缁樻媴閸涘﹥鍠愭繝娈垮枤閺佸鐛幇鏉跨畾鐟滄粓宕甸弴鐘冲枑闁哄啫鐗嗛弰銉╂煃瑜滈崜姘跺Φ閸曨垰绠抽柛鈩冦仦婢规洟姊绘担鍝ユ瀮妞ゎ偄顦靛畷褰掑锤濡も偓缁犳牗绻涢崱妯诲鞍闁搞倖鍨堕妵鍕箳閸℃ぞ澹曟俊鐐€х徊鎯ь渻閽樺娼栭柧蹇氼潐鐎氭岸鏌ょ喊鍗炲妞ゆ柨顦辩槐鎾存媴缁涘娈梺缁橆殔濡繈銆佸鑸垫櫜濠㈣泛锕﹂鎰箾鏉堝墽鍒伴柟鑺ョ矒椤㈡瑩骞掗弮鍌滐紳闂佺鏈悷褔宕濆鍡愪簻妞ゆ挾鍋為崰妯尖偓瑙勬磸閸ㄤ粙鐛弽銊﹀闁稿繐顦扮€氬ジ姊绘担鍛婂暈缂佸鍨块弫鍐晲閸ヮ煈鍋ㄩ梻渚囧墮缁夌敻鎮￠弴銏＄厪濠电偛鐏濋埀顒佹礀閻ｇ敻宕卞☉娆戝幈闂佸磭鎳撻悘婵嬫倶閼碱兘鍋撶憴鍕闁靛牊鎮傞獮鍐Χ閸℃ê顎撻柣鐘叉礌閳ь剝娅曞▍鏍⒒閸屾艾鈧兘鎳楅崜浣稿灊妞ゆ牜鍋涚粈澶愭煛瀹ュ骸鍘靛ù婊冪秺閺屾盯骞囬棃娑欑亪濠殿喛顫夐悡锟犲蓟閿濆绠涙い鏃囧Г濮ｅ嫮绱掗悙顒€鍔ら柕鍫熸倐瀵鈽夊顐ｅ媰闂佸憡鎸嗛埀顒€危閸垻纾藉ù锝呯畭娴滅偤鏌涢妷锝呭闁告ɑ鎹囬幃宄邦煥閸曨厾鐓夐悗瑙勬礃缁挻淇婂宀婃Ь缂備讲鍋撳┑鐘叉处閻撴洟鏌嶉埡浣告殶闁宠棄顦遍惀顏堝箚瑜滈悡濂告煛鐏炲墽娲寸€殿喗鎸虫俊鎼佸Ψ閵堝洨鍩嶉梻鍌欑閹碱偊顢栭崱妞㈡盯宕橀鑹版憰闂佸搫娲ㄩ崰搴ｆ閻愮儤鐓曢柍鈺佸彁閹达附鍋熼柡鍥ュ灪閳锋垿鏌熼幆鏉啃撻柡渚€浜堕弻娑㈠Ω閵壯傝檸濡炪値鍋勭换鎴犳崲濠靛棭娼╂い鎺戝閺佸綊姊绘担铏瑰笡婵﹨顫夌粋宥嗙鐎ｎ亞鍔﹀銈嗗笂缁€浣虹箔閹烘挶浜滄い鎾偓鍐插Х濡炪倧绠掑▍鏇犳崲濞戙垹鐭楀鑸殿焽閸旂兘姊洪悷鎵暛闁搞劌缍婇崺銉﹀緞婵犲孩鍍靛銈嗘尵閸嬬喕銇愰幘顔界厽闁绘柨鎽滈惌濠勭磼婢跺﹦绉哄┑鈩冩尦瀹曘劑骞栭鐔告珜闂備線鈧偛鑻晶瀛樼節閳ь剚鎷呯化鏇熸杸闂佺粯顭堥婊冾啅閵夆晜鐓欑€瑰嫰鍋婇崕鏃堟煙椤旀儳浠﹂柕鍫秮瀹曟﹢鍩￠崘銊ョ瑲闂備浇宕甸崰鎰版偡閵壯€鍋撳鐓庡⒋闁诡喗锕㈤崺锟犲川椤旀儳甯楅柣鐔哥矋缁挸鐣峰鍫澪╃憸蹇曠矆婵犲洦鐓曢柍鈺佸暟閳藉鐥幆褜鐓奸柡灞界Х椤т線鏌涢幘璺烘灈鐎殿喖顭烽幃銏ゅ礂閼测晛寮抽梺璇插嚱缂嶅棝宕戞担鍦浄闁靛繒濮弨鑺ャ亜閺冨倶鈧寮ㄧ紒妯圭箚闁绘劘鍩栭ˉ澶愭煟閿濆洤鍘村┑鈩冩倐閺佸倿宕滆濡插洭姊绘担鍛婂暈婵炶绠撳畷銏°偅閸愩劍杈堥梺闈涚墕椤︿即鍩涢幋锔藉仯闁搞儯鍔岀徊缁樸亜閹哄鐏查柡灞诲€涢妵鎰板箳閺冨倹姣囬柣搴ゎ潐濞叉﹢鎮￠敓鐘靛祦闁规崘顕х粻鎶芥煙鐎电袨闁稿甯楃换婵嬫偨闂堟刀銉╂煛娴ｈ鍊愮€规洘鍨甸埥澶娢熷鍛瀾缂佺粯绻堝畷姗€顢斿鍡涙暅濠电姷鏁告繛鈧繛浣冲浂鏁勯柛鈩冪☉绾惧鏌涘畝鈧崑鐐烘偂濞戙垺鐓曢柕澶涚到閸旀岸鏌ｈ箛锝勯偗闁哄矉缍侀獮妯兼崉閻戞鈧偓绻涢敐鍛悙闁挎洦浜妴浣糕槈濡攱鏂€闂佺硶鍓濋〃鍡涘磿椤忓牊鈷掑ù锝呮啞閸熺偤鏌ｉ悢鏉戠伈鐎规洘鍨块獮妯肩磼濡攱瀚藉┑鐐舵彧缁蹭粙骞夐敓鐘茬柈闁绘劗鍎ら悡鐔兼煟閺冣偓濞兼瑩宕濋妶澶嬬厓鐟滄粓宕滃璺虹鐟滅増甯掗惌妤呮煕閹伴潧鏋涙潻婵嬫⒑閸涘﹤濮﹂柛鐘崇墪閺侇噣姊绘担绋挎毐闁圭⒈鍋婂畷鎰板箹娴ｅ摜鍔﹀銈嗗笒閸婃悂宕㈤幘顔界厸鐎光偓閳ь剟宕伴幘鑸殿潟闁圭儤鍤﹂悢鍏兼優闁革富鍘介崵鍐ㄢ攽閻樺灚鏆╅柛瀣洴閹冾煥閸繄鐓戦梺鍛婂姦閸犳牠鎷戦悢鐑樺枑闊洦娲橀～鏇㈡煙閻戞ê娈鹃柣鏂垮悑閸嬪倿骞栫€涙〞鎴犫偓姘叀濮婂宕掑▎鎴М闂佸湱鈷堥崑濠傤嚕閻㈠壊鏁嗛柛鏇ㄥ墮閸擃喖顪冮妶鍡欏⒈闁稿鍠庨悾鍨瑹閳ь剟寮诲☉銏犖ㄦい鏃傚帶椤晠鏌熼婊冩灈婵﹥妞介獮鎰償閳垛晜瀚介梻浣告惈閹峰宕戞径鎰﹂柟鐗堟緲瀹告繃銇勯弽銊х煂闁挎稒绻冪换娑欐綇閸撗勫仹濡炪値鍘奸悧鎾诲春濞戙垹绫嶉柛顐ゅ枔閸欏嫰妫呴銏″闁圭懓娲畷锝夊礋椤撴稑浜鹃悷娆忓缁€鈧紓鍌氱Т閿曘倝鎮鹃柨瀣檮缂佸鐏濆畵鍡涙⒑缂佹ê濮岄柛鈺傜墵楠炲瀵肩€涙ǚ鎷绘繛杈剧悼閹虫捇顢氬鍛＜閻犲洦褰冮埀顒佺摃閻忓鈹戦悙鍙夘棡闁圭鎽滄竟鏇㈠锤濡や胶鍘介梺鍝勫€搁悘婵嬪箖閹达附鐓熼柟鎯у暱閺嗭綁鏌＄仦鐣屝ｆ繛纰变邯楠炲秹顢氶崨顔ф粓姊绘担鍛婃儓婵☆偄閰ｅ畷瑙勭節濮橆厼鍓﹀銈呯箰閻楁粓寮崶銊х闁瑰浼濋崗鑲╃彾闁哄洨鍠撶弧鈧梺姹囧灲濞佳冩毄闂備浇妗ㄧ粈渚€骞夐敓鐘茬疄闁靛ň鏅滈崑銊╂煕閹惧啿绾ч柡鍛櫊濮婃椽宕崟顓涙瀱闂佸憡顭堥崑鎰垝閿濆憘鏃€鎷呴悷鏉夸紟婵犵妲呴崹杈┾偓绗涘懏鍏滃Δ锝呭暞閻撴盯鎮楅敐鍌涙珖缂佹劖妫冮弻锛勪沪閸撗€妲堥梺瀹狀潐閸ㄥ灝鐣烽悢纰辨晝闁靛繒濯娑㈡⒒閸屾瑧鍔嶉柟顔肩埣瀹曟繂顓奸崶銊ュ簥闂佺鐬奸崑娑㈡偂濮椻偓閺岀喐娼忔ィ鍐╊€嶉梺绋款儐閸旀瑩寮诲☉妯锋瀻闊浄绲炬闂備線娼ч悧鍐疾閻樺樊娼栭柣鎴炆戞慨婊堟煙濞堝灝娅樻俊宸枛椤啴濡堕崱妤冧淮濡炪倧绠撳褔顢氶敐鍥ㄥ珰鐎瑰壊鍠栭幃鎴︽⒑閸撴彃浜介柛瀣嚇椤㈡捇宕堕浣叉嫽婵炶揪绲介幉锟犲疮閻愮儤鐓欓柟闂磋兌閻ｈ櫣鈧娲滄晶妤呭箚閺冨牃鈧箓骞嬮悙瀛樼彣闂傚倷鐒︾€笛呮崲閸屾娲晜闁款垰浜炬慨姗嗗幘椤ｈ尙绱掔紒妯兼创鐎殿喖鐖奸獮瀣敇閻愭彃顥庡┑锛勫亼閸娿倝宕戦崟顓犵煋闁荤喖鍋婂鏍ㄧ箾瀹割喕绨兼い銉ョ墛缁绘盯骞嬮悙瀵告濡炪倖鏌ㄩ敃銉ф崲濠靛棌鏋旈柛顭戝枟閻忔捇姊虹粙璺ㄧ闁挎洏鍨芥俊瀛樻媴缁洘鐎婚梺褰掑亰閸犳岸鎯侀崼銉︹拺闁硅偐鍋涢崝姗€鏌涢弬娆炬█妤犵偛绻愮叅妞ゅ繐鎳夐幏娲⒒閸屾氨澧愰柡鍛洴閹礁顭ㄩ崼鐔哄幈濠碘槅鍨伴幖顐﹀箖閹寸姷纾奸柛灞炬皑鏍￠梺闈涚墳缂嶄礁鐣峰鈧崺锟犲礃閵娿儳鐤勯梻鍌氬€烽懗鍫曞箠閹惧瓨娅犲ù鐘茬懁婢舵劕绠涙い鎾跺Х瑜版儳鈹戦濮愪粶闁稿鎹囬弻鐔兼寠婢跺苯鐓熼梺璇″枟閻熲晠骞冨鍏剧喖鎮℃惔锛勭杽闂傚倸鍊烽悞锕傚几婵傜鐤炬繛鎴欏灩閻ゎ噣鏌曟繝蹇擃洭妞も晠鏀辩换婵囩節閸屾粌顤€闂佺粯鎸婚惄顖炲蓟瀹ュ牜妾ㄩ梺鍛婃尰濮樸劎鍒掔€ｎ喖绠抽柡鍌氭惈娴滈箖鏌ㄥ┑鍡涱€楀ù婊呭仱閺屾稑螣閸︻厾鐓撳┑顔硷躬缂傛岸濡甸幇鏉跨闁瑰瓨绮岄弸鍫ユ⒒娴ｈ鍋犻柛鏂跨箲缁傚秹顢楅埀顒勫煡婢舵劖鍋ㄧ紒瀣硶椤︻參鎮峰鍐濠㈣娲樼缓浠嬪川婵犲嫬骞嶉梻浣告贡缁垳鏁埡鍛？闁硅揪闄勯悡鐔兼煥濠靛棙澶勯柡鍡╁墴閺屸€崇暆鐎ｎ剛锛熸繛瀵稿缁犳挸鐣峰鍡╂Х濠碘剝褰冮悧鎾诲蓟瑜忕槐鎺懳熼悡搴樻嫲闂備礁鎼懟顖滅矓閻戦摪銊︾瑹閳ь剟寮诲☉銏犵閻犺櫣鍎ら悗濠氭⒑娴兼瑧鎮奸柛蹇旓耿閵嗕礁鈽夐姀鈥斥偓鐑芥煛鐏炶鍔滈柡鍡楁噺缁绘繂顕ラ柨瀣凡闁逞屽墯濞茬喖寮崘顔嘉ㄩ柍杞拌兌閺屟冾渻閵堝懐绠伴柣妤€锕崺娑㈠箣閿旂晫鍘电紓浣割儐鐎笛囧箲閿濆洨纾奸柣妯挎珪鐏忔澘菐閸パ嶈含妞ゃ垺娲熼弫鎰板炊閵娿儱鐏￠梻鍌欑窔濞佳兾涘Δ鍛疇婵せ鍋撴鐐插暙椤劑宕奸悢閿嬬枀闂備線娼чˇ顓㈠磿椤曗偓瀹曟垿骞樼紒妯轰缓闂佸憡绋戦敃锕傚矗閸℃せ鏀介柣妯肩帛濞懷勪繆椤愶絿娲寸€规洘鐟╁畷鐑筋敇閻樼绱查梻渚€娼ч…鍫ュ磹濡ゅ懏鍎楁繛鍡樻尰閻撴盯鎮橀悙鎻掆挃闁愁垱娲滅槐鎺旂磼濡偐鐤勯悗瑙勬礈閸犳牠銆侀弴銏℃櫖闁告洦鍓欑粈瀣節绾板纾块柛瀣灴瀹曟劙濡堕崱娆樻锤濠电姴锕ら悧鍡涙偪椤曗偓閹鈽夊▍顓″亹閹广垽宕卞☉娆戝幘缂備礁顑堝▔鏇熺濞戙垺鐓曢幖杈剧到閺嬫盯鏌＄仦鐣屝у┑锛勫厴婵＄柉顧傜紒杈╁仜椤啴濡堕崱妯锋嫻闂佸憡姊瑰ú鐔煎春閻愬搫绠ｉ柨鏃囨娴滃湱绱撻崒娆戝妽閽冮亶姊哄▎鎯у籍婵﹨娅ｇ划娆撳礌閳ュ啿顫犻梻浣侯攰濞呮洟骞戦崶顒佹櫜闁绘劕澧庨悿鈧┑鐐村灦閻熴儱鈻撻妷鈺傗拺闂傚牊绋撴晶鏇㈡煙閸愭煡鍙勯柟顔缴戠换婵嬪炊閵娿垺瀚奸梻浣告啞閹告槒銇愰崘鈺冾洸闁绘劗鍎ら悡鏇㈡煟濡寧鐝€规洖鐭傞弻鐔碱敊閻愵剛鍔归梺闈涙处閸旀瑩鐛幒妤€绠婚悹鍝勬惈缁楁岸姊洪懡銈呮瀾缂侇喖绉堕崚鎺楀箻瀹曞洦娈惧┑鐘诧工閻楀﹪宕戦崟顖涚厽闁规儳鍟块鍌炴煏婢跺牆鍓憸鐗堝笚閺呮煡鏌涘☉鍗炲季婵☆偄鑻埞鎴︽倷閼碱剚鐧侀梺鍝勬噽婵炩偓鐎殿喖顭锋俊鍫曞炊閳哄啰鍘梺鑽ゅУ娴滀粙宕濈€ｎ剙鍨濋梻鍫熺▓閺€浠嬫煟閹邦剙绾ч柛锝堟缁辨帡顢欓懞銉ョ濡炪値鍋勭换鎰弲濡炪倕绻愮€氼噣藝椤撱垺鈷戦柛锔诲幘鐢盯鎮介姘惧姛闁兼椽浜堕獮姗€顢欑憴锝嗗闂備胶顢婇崑鎰板磻濞戞瑤绻嗛柛蹇曨儠娴滄粍銇勯幘璺轰粶婵¤尙绮妵鍕即椤忓棛袦閻庤娲栭妶绋款嚕閹绢喗鍊锋繛鍫濈仢閺咃絾绻濋悽闈涗哗闁规椿浜炲濠冪鐎ｎ亜鍋嶅┑鐘诧工閻楀棛绮婚娑氱鐎瑰壊鍠曠花濂告煃闁垮鐏撮柡灞剧☉閳藉顫滈崼婵嗩潬缂傚倷鑳舵慨鐢稿箲閸ヮ剙绠栨俊銈傚亾妞ゎ偅绻堥幃鈩冩償閿涘嫷鍟囧┑锛勫亼閸婃牠寮婚妸褎宕查柟鐗堟緲閻撴﹢鏌熺€电袥闁稿鎹囬弫鎰償閳ヨ尙鏁栭梻浣告啞閿曘垺绂嶇捄渚綎闁惧繐婀辩壕鍏兼叏濡も偓濡盯宕濈粙搴撴斀闁绘劕寮堕崳鐑樼箾閸欏澧甸柟顔藉劤閻ｏ繝骞嶉鑺ョ暦闂備線鈧偛鑻晶鎾煕閳规儳浜炬俊鐐€栫敮濠勬閿熺姴鐤煫鍥ㄧ⊕閻撴洟鏌ｅΟ璇插婵炲牊娲滅槐鎺旂磼濡皷濮囩紓浣虹帛缁诲牆鐣烽幆閭︽Ь闂佷紮绲惧钘夘潖濞差亜绀冮柛娆忣槹閸庢捇姊洪悷鏉挎毐缂佺粯锕㈤悰顕€宕卞☉娆忊偓閿嬬箾閿濆骸鍘哥紒銊ヮ煼濮婅櫣鎲撮崟顐闂佸搫鎳忛惄顖炲箖濮椻偓閸┾剝瀵奸崡鐐电Ш闁诡喒鍓濋幆鏃堝Ω閵夈儱寮峰┑鐘愁問閸犳牠鏁冮敂鎯у灊妞ゆ牜鍋涚粻顖炴煕濞戞瑦缍戠€瑰憡绻傞埞鎴︽偐閸欏娅у銈冨灩閹虫ê顫忕紒妯诲濞撴凹鍨抽崝鍝ョ磽娴ｉ潧濡芥俊鐐舵閻ｇ兘骞囬鑺ユ杸闁诲函缍嗛崜娆戠矈閿曞倹鈷戠憸鐗堝笒娴滀即鏌涘Ο铏圭Ш鐎规洘鍨垮畷銊р偓娑欘焽閸橀亶姊虹憴鍕棎闁哄懏绋掓穱濠囧锤濡や胶鍘卞┑鈽嗗灥椤曆勬叏瀹ュ棙鍙忓┑鐘插暞閵囨繄鈧娲﹂崑濠傜暦閻旂⒈鏁嗛柍褜鍓涚划锝呪槈閵忊檧鎷洪梺鍛婄缚閸庡崬鐡繝纰樻閸嬪懘鎮疯閸掓帞鈧綆浜堕崥瀣煕濠娾偓閼冲爼宕ｉ崱娑欌拺闁告稑锕ョ壕鐢告煛閸涱喚鎳呴柤楦块哺缁绘繂顫濋娑欏闂佽崵鍠愰悷銉р偓姘煎墰缁牓宕橀埡鍐啎婵犮垼娉涢鍥煀閺囩姷纾奸柛灞剧☉缁椻晜銇勯敃鈧鍫曞Φ閸曨垼鏁囬柍銉ュ暱婵嘲顪冮妵鍗炲暙閳ь剙鐏濋～蹇旂節濮橆剛顦板銈嗗姂閸╁嫭瀵奸崘鈺冪瘈缁炬澘顦辩壕鍧楁煛娴ｇ瓔鍤欓柣锝囧厴閹垻鍠婃潏銊︽珫婵犳鍠楅敋闁告艾顑囩槐鐐哄磼閻愮补鎷绘繛杈剧到閹芥粓寮搁崘鈺€绻嗘い鎰╁灩椤忊晠鎽堕悙瀵哥闁瑰瓨鐟ラ悘鈺冪磼閳ь剚寰勬繝搴㈠瘜闁诲函缍嗘禍婵嬪箲閿濆洨妫柟瑙勫姈椤ュ妫佹径鎰叆婵犻潧妫楅顐︽煟椤撶喓鎳囬柡灞剧☉閳规垿宕堕妸锝勮檸闂備浇顕栭崰鏇犲垝濞嗘挶鈧礁鈽夊Ο閿嬵潔濠碘槅鍨抽埛鍫ュ磿鎼淬劍鈷掑ù锝囩摂閸ゆ瑧绱掔紒妯虹仼闁轰緡鍣ｉ崹楣冨箛娴ｅ湱绋佸┑鐘垫暩婵敻鎳濋崜褍顥氶柛蹇涙？缁诲棝鏌曢崼婵嗏偓鍛婄閻愵剛绠鹃悗娑欘焽閻帞绱掗悩宕囧ⅹ妞ゎ偄绻戦妶锔炬啑閵堝嫭鐫忛梻浣告贡閸庛倝宕归幎钘夌獥濠电姴娲﹂埛鎴︽煕濠靛嫬鍔氶弽锟犳⒑閻撳海绉虹紒鐘崇墵瀹曟椽濮€閵堝懐鐫勯梺鍓插亝缁诲牓寮鍐ｆ斀閹烘娊宕愰幘鑸靛闁哄被鍎辩粻顖氣攽閻樺磭顣查柍閿嬪灩缁辨帞鈧綆鍋勯婊勭節閳ь剚瀵肩€涙鍘介梺缁樻⒐濞兼瑦鎱ㄩ崒婧惧亾鐟欏嫭绀冩い銊ユ嚇閹儳鈹戠€ｎ亞鍔﹀銈嗗笒閸婂綊锝為弴銏＄厵闁绘垶锕╁▓銏ゆ煛娴ｅ壊鍎旈柡灞剧☉閳藉宕￠悙鑼啋濠电偛顕慨鐢稿箖閸岀偛绠栨俊銈呭暞閸犲棝鏌涢弴銊ュ妞わ负鍔庣槐鎾存媴缁涘娈梺缁橆殔濡繈銆佸鑸垫櫜濠㈣泛锕﹂鎺戭渻閵堝棙鈷掗柍宄扮墕椤洦绻濋崶銊㈡嫼缂傚倷鐒﹂妴鐐哄箣閿濆啩姹楅梺鍛婂姀閺呮繈銆呴弻銉︾厾闁告縿鍎查弳鈺冪磼閳锯偓閸嬫捇姊绘担鍦菇闁搞劏妫勯…鍥槻闁烩槅鍙冨缁樻媴閻熼偊鍤嬪┑鐐村絻缁绘ê鐣烽幇顑芥斀閻庯綆浜為悾娲偡濠婂嫭鐓ラ柣锝囧厴瀹曪繝鎮欓埡鍌溾偓濠氭椤愩垺绁紒鏌ョ畺钘?
  const sidebarEl = sidebarRef.value
  const contentEl = contentRef.value
  const shellEl = shellRef.value
  const maskWrapEl = maskWrapRef.value
  const pulseEl = impactPulseRef.value
  const topLineEl = inkTopRef.value
  const bottomLineEl = inkBottomRef.value
  const panels = maskPanelRefs.value
  const titleEl = transitionTitleRef.value

  const isProbe = targetMode === 'probe'
  const accentColor = isProbe ? '#f97316' : '#3b82f6' // Orange for Probe, Blue for Defense
  transitionTitleText.value = isProbe ? 'PROBE' : 'DEFENSE'

  if (modeTimeline) {
    modeTimeline.kill()
  }

  isModeSwitching.value = true

  // Fallback
  if (!contentEl || !shellEl || !maskWrapEl) {
    void router.push(modeDefaultRoute[targetMode]).then(() => {
      isModeSwitching.value = false
    })
    return
  }

  // Ensure the new title text is rendered before GSAP snapshots transforms.
  await nextTick()
  if (titleEl) {
    // Force layout so translate(-50%, -50%) is calculated with real glyph metrics.
    void titleEl.offsetWidth
  }

  // Initial States
  gsap.set(maskWrapEl, { display: 'flex', autoAlpha: 1 })
  gsap.set(panels, { 
    scaleY: 0, 
    transformOrigin: 'top', 
    backgroundColor: isProbe ? '#0c0a09' : '#0f172a', 
    borderColor: isProbe ? 'rgba(249, 115, 22, 0.2)' : 'rgba(59, 130, 246, 0.2)'
  })
  
  if (pulseEl) {
    gsap.set(pulseEl, { 
      autoAlpha: 0, 
      scale: 0,
      borderColor: accentColor,
      boxShadow: `0 0 30px ${accentColor}`
    })
  }

  if (topLineEl && bottomLineEl) {
    gsap.set([topLineEl, bottomLineEl], { 
      scaleX: 0, 
      autoAlpha: 0,
      backgroundColor: accentColor,
      boxShadow: `0 0 20px ${accentColor}`
    })
  }

  if (titleEl) {
    gsap.set(titleEl, {
      autoAlpha: 0,
      scale: 0.8,
      x: 0,
      y: 0,
      xPercent: -50,
      yPercent: -50,
      transformOrigin: '50% 50%',
      letterSpacing: '1em',
      textShadow: `0 0 0px ${accentColor}`
    })
  }

  modeTimeline = gsap.timeline({
    onComplete: () => {
      isModeSwitching.value = false
      modeTimeline = null
      resetAnimatedState()
    }
  })

  // --- Animation Sequence (Slower & Cinematic) ---
  
  // 1. Initiate: Content scales down
  modeTimeline
    .to(contentEl, {
      filter: 'blur(4px) grayscale(80%)',
      opacity: 0.6,
      duration: 0.6,
      ease: 'power2.inOut'
    }, 0)
    .to(shellEl, {
      backgroundColor: '#000',
      duration: 0.6
    }, 0)

  if (sidebarEl) {
    modeTimeline.to(sidebarEl, {
      scaleX: 1,
      filter: 'blur(4px) grayscale(80%)',
      opacity: 0.6,
      transformOrigin: 'center center',
      duration: 0.6,
      ease: 'power2.inOut'
    }, 0)
  }

  // 2. Tech Wipe: Panels slam down (Full Cover)
  modeTimeline.to(panels, {
    scaleY: 1,
    duration: 0.7,
    stagger: {
      amount: 0.3,
      from: isProbe ? 'start' : 'end',
      grid: [1, 12]
    },
    ease: 'expo.inOut'
  }, 0.2)

  // 3. Scan Lines: Zip across during close
  if (topLineEl && bottomLineEl) {
    modeTimeline.to([topLineEl, bottomLineEl], {
      autoAlpha: 1,
      scaleX: 1,
      duration: 0.5,
      ease: 'power2.inOut'
    }, 0.3)
  }

  // 4. TITLE REVEAL (The "Middle" Moment)
  // Starts when panels are mostly down (around 0.8s)
  if (titleEl) {
    modeTimeline
      .to(titleEl, {
        autoAlpha: 1,
        scale: 1,
        letterSpacing: '0.2em', // Compress tracking
        textShadow: `0 0 30px ${accentColor}`,
        duration: 0.8,
        ease: 'power4.out'
      }, 0.7) // Start appearing as panels finish closing
      
      // Glitch shake effect
      .to(titleEl, {
        x: 2,
        y: -2,
        duration: 0.05,
        repeat: 5,
        yoyo: true,
        ease: 'steps(1)'
      }, 0.8)
      
      // Hold for a moment (0.5s pause implicit in duration)
      .to(titleEl, {
        autoAlpha: 0,
        scale: 1.5,
        x: 0,
        y: 0,
        filter: 'blur(10px)',
        letterSpacing: '0.5em',
        duration: 0.4,
        ease: 'power2.in'
      }, 1.6) // Fade out after hold
  }

  // 5. Switch Router (Hidden behind panels)
  modeTimeline.add(() => {
    void router.push(modeDefaultRoute[targetMode]).then(() => {
      gsap.set(contentEl, {
        filter: 'blur(10px) brightness(1.5)',
        opacity: 0
      })

      if (sidebarEl) {
        gsap.set(sidebarEl, {
          filter: 'blur(10px) brightness(1.5)',
          scaleX: 1,
          opacity: 0,
          transformOrigin: 'center center'
        })
      }
    })
  }, 1.2) // Switch happens while text is visible

  // 6. Reveal: Panels retract (Starts after title fades out)
  const revealStart = 1.8 // Delayed start
  
  modeTimeline.to(panels, {
    scaleY: 0,
    transformOrigin: 'bottom',
    duration: 0.7,
    stagger: {
      amount: 0.2,
      from: isProbe ? 'end' : 'start'
    },
    ease: 'expo.inOut'
  }, revealStart)

  // 7. Lines fade out
  if (topLineEl && bottomLineEl) {
    modeTimeline.to([topLineEl, bottomLineEl], {
      scaleX: 0,
      autoAlpha: 0,
      transformOrigin: isProbe ? 'right' : 'left',
      duration: 0.4
    }, revealStart + 0.1)
  }

  // 8. Energy Burst (Sync with reveal)
  if (pulseEl) {
    modeTimeline
      .set(pulseEl, { autoAlpha: 1, scale: 0.1 }, revealStart)
      .to(pulseEl, {
        scale: 4,
        autoAlpha: 0,
        duration: 0.6,
        ease: 'power2.out'
      }, revealStart)
  }

  // 9. Content Returns
  modeTimeline.to(contentEl, {
    filter: 'blur(0px) brightness(1)',
    opacity: 1,
    duration: 0.8,
    ease: 'power3.out'
  }, revealStart + 0.2)

  if (sidebarEl) {
    modeTimeline.to(sidebarEl, {
      scaleX: 1,
      scaleY: 1,
      filter: 'blur(0px) brightness(1)',
      opacity: 1,
      duration: 0.8,
      ease: 'power3.out'
    }, revealStart + 0.2)
  }
  
  // 10. Restore Shell
  modeTimeline.to(shellEl, {
    backgroundColor: '',
    clearProps: 'backgroundColor',
    duration: 0.5
  }, revealStart + 0.3)
}

const switchMode = (mode: ModeKey) => {
  if (mode === activeMode.value) return
  if (isModeSwitching.value) return
  void runModeTransition(mode)
}

const onModeChange = (nextMode: string | number) => {
  if (nextMode === 'defense' || nextMode === 'probe') {
    switchMode(nextMode)
  }
}

const goToSettings = () => {
  router.push('/settings')
}

const goToSecuritySettings = () => {
  router.push('/settings?tab=security')
}

const markAllNotificationsRead = () => {
  notifications.value = notifications.value.map((item) => ({ ...item, read: true }))
  notifPage.value = 1
}

const goToProfile = () => {
  router.push('/profile')
}

// 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁炬儳缍婇弻鐔兼⒒鐎靛壊妲紒鐐劤濠€閬嶅焵椤掑倹鍤€閻庢凹鍙冨畷宕囧鐎ｃ劋姹楅梺鍦劋閸ㄥ綊宕愰悙鐑樺仭婵犲﹤鍟扮粻鑽も偓娈垮枟婵炲﹪寮崘顔肩＜婵炴垶鑹鹃獮鍫熶繆閻愵亜鈧倝宕㈡禒瀣瀭闁割煈鍋嗛々鍙夌節闂堟侗鍎愰柣鎾存礃缁绘盯宕卞Δ鍐唺缂備胶濮垫繛濠囧蓟瀹ュ牜妾ㄩ梺鍛婃尰缁诲牓鏁愰悙鏉戠窞濠电偞甯楀钘夘嚕娴犲鈧牠鍩勯崘鈹夸虎闂佽桨绀侀崐鍧楀箰婵犲啫绶炲┑鐘插缁ㄥ瓨绻濋悽闈涗粶妞ゆ洦鍙冨畷銏ｎ樄闁诡喗妞芥俊鎼佸煛閸屾矮绨甸梻渚€娼чˇ顐﹀疾濠婂牊鍋傛繛鎴欏灪閻撴洟鏌曟径鍫濈仾婵炲懎鎳庨湁闁绘ê纾惌鎺楁煛鐏炵晫啸妞ぱ傜窔閺屾盯骞橀弶鎴濇懙濡ょ姷鍋涢崯鏉戠暦閹烘埈娼╅弶鍫涘妽椤旀洟鏌ｉ悢鍝ョ煂濠⒀勵殘閺侇噣骞掗弬娆炬婵犻潧鍊搁幉锟犳偂閻斿吋鐓欓梺顓ㄧ畱婢у鏌涢妶鍥ф灈闁哄本绋戣灒闁稿繐鍚嬪В鍫濃攽椤旂》榫氭繛鍜冪秮楠炲繘鎮╃拠鑼紜閻庤娲栧ú锝夊礌閺嵮€鏀介柣姗嗗亝婵即鏌涢弴鐐典粵闁汇倓绶氶弻锕€螣閻撳孩鐎诲銈庡幖濞硷繝骞婂鍫燁棃婵炴垶锕╁鏃堟⒒娴ｈ櫣甯涢柟绋款煼閹嫰顢涢悙鑼暫濠德板€曢幊蹇涘疾閺屻儲鐓曢悘鐐插⒔閳洟鏌ｅ┑鍥╁⒈缂佽鲸鎸婚幏鍛存偡閺夋娼旀繝娈垮枛閿曘倝鈥﹂悜钘夋槬闁逞屽墯閵囧嫰骞掑鍥獥闂佸摜鍠庣换姗€寮诲☉銏″亹鐎规洖娲ら埛宀勬⒑鐠団€虫灁闁稿海鏁婚獮鍐焺閸愨晛鍔呴梺鎸庣箓濡瑩顢欓弴銏♀拻濞达綀娅ｇ敮娑㈡煙缁嬫寧鎲搁柤楦夸含閹瑰嫭鎷呴弴顏嗙М鐎规洖銈搁幃銏ゅ礈娴ｈ櫣鏆板┑锛勫亼閸婃牠鎮уΔ鍛仭闁靛ň鏅╅弫鍡涙煟閺傚灝鎮戦柣鎾跺枛楠炴牕菐椤掆偓閻忣亞绱撳鍡楃伌闁哄苯绉堕幉鎾礋椤愩倓绱濋梻浣筋嚃閸犳鎮烽埡鍛疇闁绘ɑ妞块弫鍡椕归敐鍥ㄥ殌闁哄鐩濠氬磼濞嗘垵濡介梺璇″枛閻栫厧鐣烽幇鏉垮嵆闁靛骏绱曢崢鎰版⒑閹稿海绠撻柟铏姍瀵娊鏁冮崒娑氬幍闂佺粯顨呴悧濠勬閺屻儲鐓曢柟鑸妼娴滄儳鈹戦敍鍕杭闁稿﹥鐗犲畷婵婎槾鐎垫澘锕幊鐐哄Ψ閿曗偓閸斿懏绻濋悽闈浶㈤柛濠勬暬瀵劍绂掔€ｎ偆鍘介梺褰掑亰閸樼晫绱為幋锔界厽闊洦娲栭弸娑㈡煛鐏炲墽娲村┑鈩冩倐婵＄兘鏁冩担渚敤缂傚倸鍊风欢锟犲窗閺嶎厸鈧箓鎮滈挊澶嬬€梺褰掑亰閸樿偐娆㈤悙鐑樺€甸柨婵嗛婢ь喗顨ラ悙鎼疁婵﹦绮换婵囨償閳ヨ尙鐩庢繝鐢靛仩椤曟粎绮婚幋锔肩稏闊洦鍝庢禍褰掓煙閻戞ê娈鹃柨鏇炲€归悡鐔兼煛閸愩劍绁╅柛鐔风箻閺岋綁鎮㈤悡搴濆枈闂佺粯鎸堕崕鐢哥嵁閺嶎偀鍋撳☉娆樼劷缂佺姷鍋ら弻娑氣偓锝庡亽濞堟粍鎱ㄦ繝鍐┿仢婵☆偄鍟埥澶娾枎濡椿妫ょ紓鍌氬€风拋鏌ュ磻閹剧偨鈧帒顫濋敐鍛闂備胶纭堕弬鍌炲垂濞差亜绠氶柡鍐ㄧ墕鎯熼梺闈涳紡閸涱喗绶繝纰夌磿閸嬫垿宕愰弽顓炶摕闁靛闄勫▍鐘绘煢濡尨绱氶柨婵嗩槸閻愬﹥銇勯幒宥堫唹闁归绮换娑欐綇閸撗呅氬銈庡亜椤﹂潧鐣烽幋锔藉亹缂備焦顭囬崢閬嶆煙閸忓吋鍎楅柛鐘崇墵閹﹢鏁傞柨顖氫壕閻熸瑥瀚粈鍐磼鐠囨彃鏆ｆ鐐叉瀵噣宕煎顏佹櫊閺屾洘寰勯崼婵嗗婵炲瓨绮岄悥鐓庮潖缂佹ɑ濯撮柛娑橈工閺嗗牏绱撴担鍓插剱闁搞劌娼″顐﹀礃椤旇姤娅嗛梺璇″瀻閸愬啯宀稿娲焻閻愯尪瀚板褍鐡ㄩ幈銊︾節閸愨斂浠㈠┑鈽嗗亜閸燁偊鍩ユ径鎰潊闁靛繒濮甸妵婵堢磽閸屾艾鈧嘲霉閸パ屽殨闁规崘娉涢崹婵囩箾閸℃ɑ灏紒鐘崇墵閺屻劑鎮㈤崫鍕戙垻绱掗悩宕団姇闁靛洤瀚板顒勫垂椤旇瀵栭梻浣瑰缁嬫帞鍒掗幘璇茶摕闁挎繂妫欓崕鐔搞亜閺嶃劎鐭岄弽锟犳⒒娴ｄ警鐒炬い鎴濇嚇楠炲﹪骞囬鐙€娲搁梺褰掓？閻掞箓宕戦妸褏妫柣妤€鐓鍛洸闁绘劦鍓涚粻楣冩煕椤愶絿绠樺ù鐘灲閺岋繝宕卞Ο鍏煎櫚闂佸搫鏈惄顖涗繆閻戣棄绠ｆ繝闈涙搐濞咃絾绻濆▓鍨珯闂傚嫬瀚粚杈ㄧ節閸ャ劌鈧攱銇勮箛鎾愁仱闁稿鎹囧浠嬵敃閿濆棙顔囬梻浣告贡閸庛倝寮婚敓鐘茬；闁圭偓鍓氬鈺呮煟閹炬娊顎楃紒顐㈢Ч濮婅櫣鍖栭弴鐔哥彆闂佺儵鏅╅崹鍫曟偘椤旈敮鍋撻敐搴℃灍闁哄懏绮撻幃宄扳枎濞嗘垹蓱闁诲孩鑹鹃崥瀣┍婵犲洦鍊锋い蹇撳閸嬫捇寮介鐐殿槷闂佺鎻粻鎴犲瑜版帗鐓涢柛銉㈡櫅閺嬫梹銇勯埡鍛暠缂佺粯绻冪换婵嬪磼濠婂喚鏉搁梻浣虹帛閹哥偓鎱ㄩ悽鍨床婵炴垯鍨洪崵鎴澪涢悧鍫㈢畵婵炲牜鍙冨铏规嫚閺屻儳宕紓浣虹帛缁诲牆顕ｆ繝姘櫢闁绘ɑ褰冪粣娑橆渻閵堝棙灏靛┑顔芥尦閹繝鎮㈡總澶嬪瘜闂侀潧鐗嗛崯顐︽倶椤忓棛纾奸悗锝庡亜閻忔挳鏌涢埞鍨姕鐎垫澘瀚换娑㈠閳╁喚妫冮悗瑙勬礃閿曘垽銆侀弮鍫濆耿婵☆垵宕靛Σ銉╂⒒閸屾艾鈧悂宕愰幖浣哥９濡炲娴烽惌鍡椼€掑锝呬壕濡ょ姷鍋涢ˇ鐢稿极閹剧粯鍋愰柛鎰紦閻㈠姊绘笟鈧褔藝椤愶箑鏋侀柨鐔哄Т閻愬﹥銇勯幒鎴Ч闁哄拋鍓欓埞鎴︽偐鐠囇冧紣闂佺娅曢崝娆撳箖妤ｅ啫閱囬柡鍥╁枎娴狀厼鈹戦悩璇у伐闁哥噥鍨堕獮鎴︽晲婢跺鍘?
let progressTimer: ReturnType<typeof setTimeout> | null = null

watch(() => route.fullPath, () => {
  isRouteChanging.value = true
  routeProgress.value = 0.25
  
  if (progressTimer) clearTimeout(progressTimer)
  
  progressTimer = setTimeout(() => {
    routeProgress.value = 0.68
  }, 180)
  
  nextTick(() => {
    setTimeout(() => {
      routeProgress.value = 1
      setTimeout(() => {
        isRouteChanging.value = false
        routeProgress.value = 0
      }, 220)
    }, 120)
  })
})

onMounted(() => {
  initTheme()
  loadSidebarPreference()
  sidebarAnimatedWidth.value = getSidebarTargetWidth()

  const user = parseStoredUserInfo()
  if (user) {
    username.value = user.username || 'user'
    role.value = user.role || 'viewer'
  }

  resetAnimatedState()
})

onUnmounted(() => {
  if (modeTimeline) {
    modeTimeline.kill()
    modeTimeline = null
  }
  if (progressTimer) {
    clearTimeout(progressTimer)
    progressTimer = null
  }
  stopSidebarResize()
  stopSidebarWidthAnimation()
})

const handleLogout = async () => {
  try {
    await authApi.logout()
  } catch (err) {
    console.error('Logout failed:', err)
  } finally {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
    router.push('/login')
  }
}
</script>

<style scoped>
.sidebar-item-label {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  transform-origin: left center;
  transition: opacity 220ms ease, transform 220ms ease;
}

.sidebar-item-label-expanded {
  max-width: 9rem;
  opacity: 1;
  transform: translateX(0);
}

.sidebar-item-label-collapsed {
  max-width: 0;
  opacity: 0;
  transform: translateX(-6px);
}

.sidebar-mode-label {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  transition: opacity 220ms ease, transform 220ms ease;
}

.sidebar-mode-label-expanded {
  max-width: 10rem;
  opacity: 1;
}

.sidebar-mode-label-collapsed {
  max-width: 2.5rem;
  opacity: 0.95;
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-item-label,
  .sidebar-mode-label {
    transition: none;
  }
}
</style>


