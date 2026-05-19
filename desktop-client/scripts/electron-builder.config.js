/**
 * Electron Builder Configuration
 */
module.exports = {
  appId: "com.gogoshine.capcut-mate",
  productName: "剪映小助手",
  protocols: [
    {
      name: "CapCut Mate Draft",
      schemes: ["capcut-mate"],
    },
  ],
  directories: {
    output: "dist"
  },
  files: [
    "**/*",
    // "!node_modules",
    "!web",
    "!dist",
    "!electron-builder.config.js",
    "!.gitignore",
    "!.github",
    "!README.md",
    "!.vscode",
    "!DS_Store",
  ],
  win: {
    icon: "assets/icons/logo.ico",
    target: "nsis",
    artifactName: "capcut-mate-windows-x64-installer.exe",
    // 本地打包勿拉 winCodeSign（Windows 无 symlink 权限时会解压失败）
    signAndEditExecutable: false,
    signingHashAlgorithms: [],
  },
  nsis: {
    oneClick: false,
    allowToChangeInstallationDirectory: true,
  },
  mac: {
    icon: "assets/icons/logo.icns",
    target: [
      {
        target: "dmg",
        arch: "arm64"
      },
      {
        target: "dmg",
        arch: "x64"
      }
    ],
    artifactName: "capcut-mate-macos-${arch}-installer.dmg",
    category: "public.app-category.productivity",
    hardenedRuntime: true,
    gatekeeperAssess: false,
    entitlements: "assets/entitlements.mac.plist",
    entitlementsInherit: "assets/entitlements.mac.plist"
  },
  dmg: {
    background: null,
    window: {
      width: 540,
      height: 380
    },
    contents: [
      {
        x: 130,
        y: 150,
        type: "file"
      },
      {
        x: 410,
        y: 150,
        type: "link",
        path: "/Applications"
      }
    ]
  }
};