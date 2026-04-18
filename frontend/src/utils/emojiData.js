const item = (emoji, name, keywords = []) => ({
  emoji,
  name,
  keywords
})

export const EMOJI_GROUPS = [
  {
    key: 'common',
    label: '常用',
    emojis: [
      item('😀', '开心', ['笑', '高兴', 'smile', 'happy', 'grin']),
      item('😄', '大笑', ['笑', '开心', 'laugh', 'happy']),
      item('😂', '笑哭', ['笑', '哭', 'laugh', 'tears']),
      item('😊', '微笑', ['笑', '开心', 'smile', 'blush']),
      item('😉', '眨眼', ['wink', '调皮']),
      item('😍', '花痴', ['爱心眼', '喜欢', 'love', 'heart eyes']),
      item('😘', '亲亲', ['kiss', '喜欢', '爱']),
      item('😎', '酷', ['cool', '墨镜']),
      item('🤔', '思考', ['想', 'question', 'think']),
      item('😭', '大哭', ['哭', '伤心', 'sad', 'cry']),
      item('😡', '生气', ['愤怒', 'angry', 'mad']),
      item('👍', '点赞', ['好', '同意', 'like', 'yes']),
      item('👎', '点踩', ['不好', '反对', 'no', 'dislike']),
      item('👏', '鼓掌', ['applause', '赞同']),
      item('🙏', '感谢', ['拜托', '谢谢', 'thanks', 'pray']),
      item('🎉', '庆祝', ['party', 'celebrate']),
      item('❤️', '红心', ['爱', 'love', 'heart']),
      item('🔥', '火', ['hot', '燃', 'fire']),
      item('✅', '完成', ['对', 'ok', 'success', 'done']),
      item('✨', '闪亮', ['sparkles', '星光']),
      item('👀', '看看', ['look', 'eyes']),
      item('😅', '尴尬', ['汗', 'awkward', 'sweat']),
      item('😮', '惊讶', ['wow', 'surprised']),
      item('😴', '困', ['睡觉', 'sleep'])
    ]
  },
  {
    key: 'smileys',
    label: '表情',
    emojis: [
      item('😀', '开心', ['smile', 'happy', 'grinning']),
      item('😃', '咧嘴笑', ['smile', 'happy']),
      item('😄', '大笑', ['laugh', 'smile']),
      item('😁', '露齿笑', ['grin', 'smile']),
      item('😆', '爆笑', ['laugh', 'funny']),
      item('🤣', '笑翻', ['rofl', 'laugh']),
      item('😊', '微笑', ['smile', 'blush']),
      item('😇', '天使', ['angel', 'innocent']),
      item('🙂', '略笑', ['smile']),
      item('🙃', '倒脸', ['upside down', 'sarcasm']),
      item('😉', '眨眼', ['wink']),
      item('😍', '花痴', ['love', 'heart eyes']),
      item('😘', '亲亲', ['kiss']),
      item('😋', '馋', ['yummy', 'tongue']),
      item('😎', '酷', ['cool', 'sunglasses']),
      item('🤩', '崇拜', ['star eyes', 'excited']),
      item('🤔', '思考', ['think']),
      item('🤗', '抱抱', ['hug']),
      item('🤭', '偷笑', ['giggle', 'oops']),
      item('😐', '无语', ['meh', 'neutral']),
      item('😑', '面无表情', ['blank', 'expressionless']),
      item('😶', '沉默', ['silent']),
      item('😏', '坏笑', ['smirk']),
      item('😒', '不爽', ['unamused']),
      item('😞', '失望', ['disappointed']),
      item('😔', '难过', ['sad', 'pensive']),
      item('😢', '流泪', ['sad', 'cry']),
      item('😭', '大哭', ['sob', 'cry']),
      item('😤', '憋气', ['steam', 'annoyed']),
      item('😡', '生气', ['angry']),
      item('🤯', '震惊', ['mind blown']),
      item('😱', '尖叫', ['scream', 'scared']),
      item('😴', '困', ['sleep']),
      item('😷', '口罩', ['sick', 'mask'])
    ]
  },
  {
    key: 'people',
    label: '人物',
    emojis: [
      item('👍', '点赞', ['like', 'yes']),
      item('👎', '点踩', ['dislike', 'no']),
      item('👌', '可以', ['ok', 'fine']),
      item('✌️', '胜利', ['victory', 'peace']),
      item('🤟', '爱你手势', ['love you']),
      item('🤘', '摇滚', ['rock']),
      item('👏', '鼓掌', ['applause']),
      item('🙌', '举手欢呼', ['celebrate', 'hooray']),
      item('🙏', '感谢', ['thanks', 'pray']),
      item('💪', '加油', ['strong', 'muscle']),
      item('🫶', '比心', ['heart hands', 'love']),
      item('🤝', '握手', ['deal', 'handshake']),
      item('👋', '挥手', ['hello', 'bye']),
      item('🫡', '敬礼', ['salute']),
      item('✍️', '书写', ['write']),
      item('💅', '美甲', ['nails', 'sass']),
      item('👀', '双眼', ['look']),
      item('🧠', '大脑', ['brain', 'idea']),
      item('👂', '耳朵', ['listen', 'ear']),
      item('❤️‍🔥', '炽热的心', ['love', 'heart on fire']),
      item('💔', '心碎', ['broken heart', 'sad']),
      item('👨‍💻', '男程序员', ['developer', 'coder']),
      item('👩‍💻', '女程序员', ['developer', 'coder']),
      item('🧑‍🚀', '宇航员', ['astronaut', 'space'])
    ]
  },
  {
    key: 'nature',
    label: '自然',
    emojis: [
      item('🌞', '太阳', ['sun', 'weather']),
      item('🌙', '月亮', ['moon', 'night']),
      item('⭐', '星星', ['star']),
      item('🔥', '火焰', ['fire', 'hot']),
      item('🌈', '彩虹', ['rainbow']),
      item('☁️', '云', ['cloud']),
      item('🌧️', '下雨', ['rain']),
      item('❄️', '雪花', ['snow']),
      item('🌸', '樱花', ['flower', 'blossom']),
      item('🌻', '向日葵', ['sunflower']),
      item('🍀', '四叶草', ['luck', 'clover']),
      item('🌲', '松树', ['tree', 'forest']),
      item('🌵', '仙人掌', ['cactus']),
      item('🌊', '海浪', ['wave', 'sea']),
      item('🐶', '小狗', ['dog', 'pet']),
      item('🐱', '小猫', ['cat', 'pet']),
      item('🐼', '熊猫', ['panda']),
      item('🦊', '狐狸', ['fox']),
      item('🐰', '兔子', ['rabbit', 'bunny']),
      item('🐻', '小熊', ['bear']),
      item('🐧', '企鹅', ['penguin']),
      item('🦋', '蝴蝶', ['butterfly']),
      item('🐬', '海豚', ['dolphin']),
      item('🦄', '独角兽', ['unicorn'])
    ]
  },
  {
    key: 'food',
    label: '食物',
    emojis: [
      item('🍎', '苹果', ['apple', 'fruit']),
      item('🍉', '西瓜', ['watermelon', 'fruit']),
      item('🍇', '葡萄', ['grapes', 'fruit']),
      item('🍓', '草莓', ['strawberry', 'fruit']),
      item('🍒', '樱桃', ['cherry', 'fruit']),
      item('🍑', '桃子', ['peach', 'fruit']),
      item('🍍', '菠萝', ['pineapple', 'fruit']),
      item('🥥', '椰子', ['coconut']),
      item('🥑', '牛油果', ['avocado']),
      item('🍅', '番茄', ['tomato']),
      item('🌽', '玉米', ['corn']),
      item('🍔', '汉堡', ['burger']),
      item('🍟', '薯条', ['fries']),
      item('🍕', '披萨', ['pizza']),
      item('🌭', '热狗', ['hot dog']),
      item('🍜', '面条', ['noodles', 'ramen']),
      item('🍣', '寿司', ['sushi']),
      item('🍰', '蛋糕', ['cake', 'dessert']),
      item('🍪', '饼干', ['cookie', 'dessert']),
      item('☕', '咖啡', ['coffee']),
      item('🍵', '茶', ['tea']),
      item('🍺', '啤酒', ['beer']),
      item('🧋', '奶茶', ['bubble tea']),
      item('🥤', '饮料', ['drink'])
    ]
  },
  {
    key: 'travel',
    label: '出行',
    emojis: [
      item('🚗', '汽车', ['car']),
      item('🚕', '出租车', ['taxi']),
      item('🚌', '公交车', ['bus']),
      item('🚎', '无轨电车', ['trolleybus']),
      item('🚓', '警车', ['police']),
      item('🚑', '救护车', ['ambulance']),
      item('🚒', '消防车', ['fire engine']),
      item('🚲', '自行车', ['bike']),
      item('🛵', '踏板车', ['scooter']),
      item('✈️', '飞机', ['plane', 'flight']),
      item('🚀', '火箭', ['rocket', 'space']),
      item('🚢', '轮船', ['ship']),
      item('⛵', '帆船', ['sailboat']),
      item('🗺️', '地图', ['map']),
      item('🏠', '房子', ['home', 'house']),
      item('🏡', '家', ['house with garden']),
      item('🏢', '办公楼', ['building', 'office']),
      item('🌆', '城市傍晚', ['city', 'sunset']),
      item('🌃', '夜景', ['night', 'city']),
      item('🏖️', '沙滩', ['beach', 'vacation']),
      item('⛰️', '山', ['mountain']),
      item('🗽', '自由女神像', ['statue of liberty']),
      item('🎡', '摩天轮', ['ferris wheel'])
    ]
  },
  {
    key: 'activity',
    label: '活动',
    emojis: [
      item('⚽', '足球', ['soccer']),
      item('🏀', '篮球', ['basketball']),
      item('🏈', '橄榄球', ['football']),
      item('⚾', '棒球', ['baseball']),
      item('🎾', '网球', ['tennis']),
      item('🏐', '排球', ['volleyball']),
      item('🎱', '台球', ['billiards']),
      item('🏓', '乒乓球', ['ping pong']),
      item('🏸', '羽毛球', ['badminton']),
      item('🥊', '拳击', ['boxing']),
      item('🎮', '游戏手柄', ['gamepad', 'gaming']),
      item('🎲', '骰子', ['dice']),
      item('🧩', '拼图', ['puzzle']),
      item('🎸', '吉他', ['guitar', 'music']),
      item('🎹', '钢琴', ['piano', 'music']),
      item('🎧', '耳机', ['headphones', 'music']),
      item('🎤', '麦克风', ['microphone', 'sing']),
      item('🎬', '电影', ['movie', 'clapper']),
      item('📷', '相机', ['camera', 'photo']),
      item('🎨', '绘画', ['art', 'paint']),
      item('🏆', '奖杯', ['trophy', 'win']),
      item('🥇', '金牌', ['gold medal']),
      item('🏅', '奖章', ['medal']),
      item('🎯', '命中', ['target', 'bullseye'])
    ]
  },
  {
    key: 'objects',
    label: '物件',
    emojis: [
      item('📌', '图钉', ['pin']),
      item('📎', '回形针', ['paperclip']),
      item('✂️', '剪刀', ['scissors']),
      item('🔒', '锁', ['lock']),
      item('🔑', '钥匙', ['key']),
      item('🧰', '工具箱', ['toolbox']),
      item('⚙️', '齿轮', ['gear', 'settings']),
      item('💡', '灯泡', ['idea', 'light']),
      item('🔦', '手电筒', ['flashlight']),
      item('🕯️', '蜡烛', ['candle']),
      item('💻', '笔记本电脑', ['laptop', 'computer']),
      item('⌚', '手表', ['watch']),
      item('📱', '手机', ['phone', 'mobile']),
      item('🖥️', '显示器', ['desktop', 'monitor']),
      item('⌨️', '键盘', ['keyboard']),
      item('🖱️', '鼠标', ['mouse']),
      item('🖨️', '打印机', ['printer']),
      item('📚', '书本', ['books', 'read']),
      item('✏️', '铅笔', ['pencil', 'write']),
      item('📝', '笔记', ['memo', 'note']),
      item('📦', '包裹', ['package', 'box']),
      item('🎁', '礼物', ['gift', 'present']),
      item('💎', '钻石', ['gem', 'diamond']),
      item('🪪', '证件', ['id card', 'badge'])
    ]
  },
  {
    key: 'symbols',
    label: '符号',
    emojis: [
      item('❤️', '红心', ['heart', 'love']),
      item('🧡', '橙心', ['orange heart']),
      item('💛', '黄心', ['yellow heart']),
      item('💚', '绿心', ['green heart']),
      item('💙', '蓝心', ['blue heart']),
      item('🖤', '黑心', ['black heart']),
      item('🤍', '白心', ['white heart']),
      item('💜', '紫心', ['purple heart']),
      item('💯', '满分', ['100', 'perfect']),
      item('✅', '勾选', ['check', 'ok']),
      item('❌', '叉号', ['cross', 'wrong']),
      item('⚠️', '警告', ['warning']),
      item('❓', '问号', ['question']),
      item('❗', '感叹号', ['exclamation']),
      item('⭕', '圆圈', ['circle']),
      item('⭐', '星标', ['star']),
      item('✨', '闪亮', ['sparkles']),
      item('🔥', '火焰', ['fire']),
      item('🌈', '彩虹', ['rainbow']),
      item('☀️', '晴天', ['sun']),
      item('🌙', '月夜', ['moon']),
      item('☁️', '云朵', ['cloud']),
      item('⚡', '闪电', ['lightning']),
      item('❄️', '雪花', ['snow'])
    ]
  }
]

const ASCII_ALIAS_PATTERN = /^[a-z0-9_+\- ]+$/

export const EMOJI_ITEMS = buildEmojiItems()
export const COMMON_EMOJI_ITEMS = buildCommonEmojiItems()

export function normalizeEmojiSearchText(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[:\s_-]+/g, '')
}

export function searchEmojiItems(query, options = {}) {
  const { limit = 8, includeCommonWhenEmpty = true } = options
  const normalizedQuery = normalizeEmojiSearchText(query)

  if (!normalizedQuery) {
    return includeCommonWhenEmpty ? COMMON_EMOJI_ITEMS.slice(0, limit) : []
  }

  return EMOJI_ITEMS
    .map(item => ({
      ...item,
      score: getEmojiMatchScore(item, normalizedQuery),
      matchedAlias: pickMatchedAlias(item, normalizedQuery)
    }))
    .filter(item => item.score > 0)
    .sort((left, right) => right.score - left.score || left.name.localeCompare(right.name, 'zh-CN'))
    .slice(0, limit)
}

function buildEmojiItems() {
  const emojiMap = new Map()

  EMOJI_GROUPS.forEach(group => {
    group.emojis.forEach(entry => {
      if (!entry?.emoji) return

      const existing = emojiMap.get(entry.emoji) || {
        emoji: entry.emoji,
        name: entry.name,
        keywords: [],
        aliases: [],
        searchTokens: [],
        groupKeys: [],
        groupLabels: []
      }

      existing.name = existing.name || entry.name
      existing.groupKeys.push(group.key)
      existing.groupLabels.push(group.label)

      ;[entry.name, ...(entry.keywords || [])].forEach(value => {
        if (!value) return

        if (!existing.keywords.includes(value)) {
          existing.keywords.push(value)
        }

        const normalizedToken = normalizeEmojiSearchText(value)
        if (normalizedToken && !existing.searchTokens.includes(normalizedToken)) {
          existing.searchTokens.push(normalizedToken)
        }

        if (ASCII_ALIAS_PATTERN.test(value)) {
          const alias = String(value).trim().toLowerCase().replace(/\s+/g, '-')
          if (alias && !existing.aliases.includes(alias)) {
            existing.aliases.push(alias)
          }
        }
      })

      emojiMap.set(entry.emoji, existing)
    })
  })

  return Array.from(emojiMap.values())
}

function buildCommonEmojiItems() {
  const commonEmojiSet = new Set((EMOJI_GROUPS.find(group => group.key === 'common')?.emojis || []).map(item => item.emoji))
  return EMOJI_ITEMS.filter(item => commonEmojiSet.has(item.emoji))
}

function getEmojiMatchScore(item, query) {
  if (item.emoji === query) return 260
  if (item.aliases.includes(query)) return 220
  if (item.searchTokens.includes(query)) return 200
  if (item.aliases.some(alias => alias.startsWith(query))) return 180
  if (item.searchTokens.some(token => token.startsWith(query))) return 160
  if (item.aliases.some(alias => alias.includes(query))) return 140
  if (item.searchTokens.some(token => token.includes(query))) return 120
  return 0
}

function pickMatchedAlias(item, query) {
  const aliases = item.aliases || []
  const exactAlias = aliases.find(alias => alias === query)
  if (exactAlias) return exactAlias

  const prefixAlias = aliases.find(alias => alias.startsWith(query))
  if (prefixAlias) return prefixAlias

  const containsAlias = aliases.find(alias => alias.includes(query))
  if (containsAlias) return containsAlias

  return aliases[0] || item.keywords[0] || item.name
}
