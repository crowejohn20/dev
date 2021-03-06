#gView 0.6.0
#View Module - gViewer.py
#---------------------------------------------------
#Description: Texture thumbnail browser for Mari
#Supported Versions: 2.6.x, 3.x
#Author: Ben Neall, Contact: bneall@gmail.com
#copyright Ben Neall 2016

from PySide import QtGui, QtCore
import subprocess
import threading
import json
import os
import uuid
import glob
import mari

imagemagick_mode = False

def getImageMagicFormats():
	'''hacky go at getting imagemagick formats'''
	outputs = subprocess.Popen("identify -list format", universal_newlines=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
	formats = set()
	for i in outputs[0].split("\n")[2:-6]:
		try:
			isBad=False
			entry = i.split()[0]
			entry = entry.replace("*", "")
			for x in entry:
				if x.islower():
					isBad = True
					break
				if x == "(":
					isBad = True
			if not isBad:
				formats.add(entry.lower())
		except Exception, e:
			pass
	return formats

def gViewPath():
    ''' Loops through the Mari user directories (specified in ENV Variables) to find the gView install folder '''

    for script_paths in mari.resources.path(mari.resources.USER_SCRIPTS).split(";"):
        for dirname, folder, files in os.walk(script_paths):
            if "gView" in str(folder):
                gPath = os.path.join(dirname)
                print "GVIEW Install Path: " + str(gPath)
                return gPath

def gTempDir():
    ''' Finds the OS and creates a temp directory for thumbnails '''

    gViewTempDir = ''

    if mari.app.version().isWindows():
        gViewTempDir = 'C:\\temp'
    else:
        gViewTempDir = '/tmp'

    print "GVIEW Temp Directory: " + gViewTempDir
    return gViewTempDir


###--------------------------------------------------------------------------###
### COMMON
###--------------------------------------------------------------------------###
mari_icon_path = mari.resources.path(mari.resources.ICONS)
mari_user_path = mari.resources.path(mari.resources.USER)
mari_script_path = mari.resources.path(mari.resources.USER_SCRIPTS)


###--------------------------------------------------------------------------###
### gView COMMON
###--------------------------------------------------------------------------###
gViewIconDir = os.path.join(mari_script_path, 'gView', 'Icons')
gViewTempDir = gTempDir()

gViewBmarkFile = os.path.join(mari_user_path, 'gViewBookmark.prefs')
gViewConfigFile = os.path.join(mari_user_path, 'gViewConfig.prefs')
gViewItemHPad = 20
gViewItemVPad = 10
gViewItemSize = 210
gViewSizes = [200, 900]

QtGui.QPixmapCache.setCacheLimit(51200)


###--------------------------------------------------------------------------###
### LOAD CONFIG
###--------------------------------------------------------------------------###
try:
    configFile = open(gViewConfigFile)
    config = json.load(configFile)
    gViewTempDir = config['gViewTempDir']
    gViewSizes = config['gViewSizes']
except:
    pass


###--------------------------------------------------------------------------###
### BOOKMARK SYSTEM
###--------------------------------------------------------------------------###
class GBookmarkItem(QtGui.QTreeWidgetItem):
    def __init__(self, name):
        super(GBookmarkItem, self).__init__()
        self.setText(0, name)
        self.setFlags(
                            QtCore.Qt.ItemIsEditable
                          | QtCore.Qt.ItemIsEnabled
                          | QtCore.Qt.ItemIsSelectable
                          | QtCore.Qt.ItemIsDropEnabled
                          | QtCore.Qt.ItemIsDragEnabled
                          )

        self.setIcon(0, QtGui.QIcon('%s/Folder32x32.png' % gViewIconDir))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            pass

class GBookmark(QtGui.QTreeWidget):
    pathAdded = QtCore.Signal(str)
    itemMoved = QtCore.Signal()
    currentItems = []
    pathList = []
    def __init__(self):
        super(GBookmark, self).__init__()
        self.setMinimumWidth(100)

        self.setDragDropMode(self.InternalMove)
        self.installEventFilter(self)
        self.setColumnCount(1)
        self.setAlternatingRowColors(True)
        self.setIndentation(10)
        self.setHeaderHidden(True)
        self.setEditTriggers(QtGui.QAbstractItemView.SelectedClicked)
        self.setDragEnabled(True)
        self.setSelectionMode(self.ExtendedSelection)
        self.itemChanged.connect(self.sortAllItems)
        self.itemMoved.connect(self.restoreExpandedState)
        #Style
        self.setStyleSheet("\
        QTreeWidget { alternate-background-color: rgb(105, 105, 105); } \
        ")

        #Context Menu
        self.menu = QtGui.QMenu()
        self.importAction = self.menu.addAction(QtGui.QIcon('%s/Palette.16x16.png' % mari_icon_path), 'New Group')
        #Connections
        self.importAction.triggered.connect(self.makeBlankItem)

    def eventFilter(self, sender, event):
        '''Detects when an item moves'''
        if (event.type() == QtCore.QEvent.ChildRemoved):
            self.itemMoved.emit()
        if (event.type() == QtCore.QEvent.ChildAdded):
            self.itemMoved.emit()
        return False # don't actually interrupt anything

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            self.removeBookmark()

    def contextMenuEvent(self, event):
        self.menu.exec_(event.globalPos())

    def removeBookmark(self):
        for item in self.selectedItems():
            if not item.parent():
                index = self.indexOfTopLevelItem(item)
                self.takeTopLevelItem(index)
            else:
                index = item.parent().indexOfChild(item)
                item.parent().takeChild(index)

    def sortAllItems(self):
        self.sortItems(0, QtCore.Qt.AscendingOrder)

    def buildFromPath(self, path=None, mode='multi'):
        #path = self.customPath.text()
        pathList = []
        itemList = []

        #Top Directory
        rootName = os.path.basename(path)
        rootPath = path
        rootItem = GBookmarkItem(rootName)
        rootItem.setData(0, 32, [None, rootName, rootPath])
        itemList.append(rootItem)
        self.addTopLevelItem(rootItem)

        if mode is 'multi':
            self.pathAdded.emit(rootPath)
            #Sub Directories
            for root, dirs, files in os.walk(path):
                for name in dirs:
                    if not name.startswith('.'):
                        parent = root
                        fullpath = os.path.join(root, name)
                        bookmarkData = [parent, name, fullpath]
                        parentItem = self.findParentItem(parent)
                        if parentItem:
                            newItem = GBookmarkItem(name)
                            newItem.setData(0, 32, bookmarkData)
                            parentItem.insertChild(0, newItem)
                            itemList.append(newItem)
                        self.pathAdded.emit(fullpath)

        #Build IDs
        self.setItemUUID(itemList)
        self.setParentUUID()

        #Sort and Expand
        self.sortAllItems()

    def makeBlankItem(self):
        inputText, ok = QtGui.QInputDialog.getText(self, 'Create New Group', 'Enter name:')

        if ok:
            #Keep Hierarchy
            for item in self.selectedItems():
                if item.childCount() >= 1:
                    for index in range(item.childCount()):
                        childItem = item.child(index)
                        childItem.setSelected(False)

            #"Blank" Item
            name = str(inputText)
            UUID = uuid.uuid4().hex
            bookmarkData = [None, name, UUID, None, True]
            blankItem = GBookmarkItem(name)
            blankItem.setData(0, 32, bookmarkData)
            blankItem.setIcon(0, QtGui.QIcon('%s/Folder32x32.png' % gViewIconDir))
            self.addTopLevelItem(blankItem)

            #Group Items
            for item in self.selectedItems():
                if item.parent():
                    item.parent().removeChild(item)
                else:
                    self.invisibleRootItem().removeChild(item)
                blankItem.insertChild(0, item)

    def findParentItem(self, itemParent):
        it = QtGui.QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            itemData = item.data(0, 32)
            if itemData[2] == itemParent:
                return item
            it += 1

    def setItemUUID(self, itemList):
        for item in itemList:
            name = item.text(0)
            parentUUID = None
            UUID = uuid.uuid4().hex
            fullPath = item.data(0, 32)[2]
            item.setData(0, 32, [parentUUID, name, UUID, fullPath, None])
            item.setExpanded(True)

    def setParentUUID(self):
        it = QtGui.QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            name = item.text(0)
            UUID = item.data(0, 32)[2]
            fullPath = item.data(0, 32)[3]
            expandState = item.isExpanded()
            try:
                parentItem = item.parent()
                parentUUID = parentItem.data(0, 32)[2]
            except:
                parentUUID = None
            item.setData(0, 32, [parentUUID, name, UUID, fullPath, expandState])
            it += 1

    def restoreExpandedState(self):
        it = QtGui.QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            expandState = item.data(0, 32)[4]
            item.setExpanded(expandState)
            it += 1

    def buildTreeItems(self):
        json_data = open(gViewBmarkFile)
        data = json.load(json_data)

        for item in data:
            parentUUID = item[0]
            name = item[1]
            UUID = item[2]
            fullPath = item[3]
            expandState = item[4]
            bookmarkData = [parentUUID, name, UUID, fullPath, expandState]
            parentItem = self.findParentItem(parentUUID)
            if parentItem:
                newItem = GBookmarkItem(name)
                newItem.setData(0, 32, bookmarkData)
                parentItem.insertChild(0, newItem)
                newItem.setExpanded(expandState)
            else:
                rootItem = GBookmarkItem(name)
                rootItem.setData(0, 32, bookmarkData)
                self.addTopLevelItem(rootItem)
                rootItem.setExpanded(expandState)
            if fullPath:
                self.pathAdded.emit(fullPath)

        #Sort
        self.sortAllItems()

    def saveBookmarkFile(self):
        self.setParentUUID()
        dataList = []
        it = QtGui.QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            itemData = item.data(0, 32)
            dataList.append(itemData)
            it += 1

        with open(gViewBmarkFile, 'w') as outfile:
            json.dump(dataList, outfile)


###--------------------------------------------------------------------------###
### GVIEW
###--------------------------------------------------------------------------###
class GThumbGen(QtCore.QThread):
    '''This class generates thumbnails to disc'''
    thumbGen = QtCore.Signal()
    finishGen = QtCore.Signal()
    def __init__(self, files=None):
        super(GThumbGen, self).__init__()
        self.files = files

    def generateThumb(self, source, thumb):
		if imagemagick_mode:
			### USING ImageMagick  - this implementation requires installation of imagemagic and its "convert" commandline tool.
			try:
				cmd = 'convert %s -resize 200x200 -format png %s' % (source, thumb)
				outputs = subprocess.Popen(cmd, universal_newlines=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
			except Exception, e:
				print e
				pass

		else:
			### USING QT - warning this can crash on certain OS and has limited file format support
			try:
				sourceImage = QtGui.QImage(source)
				thumbImage = sourceImage.scaled(200,200, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
				thumbImage.save(thumb, 'png', 75)
			except Exception, e:
				print e
				pass

		#Trigger finished
		self.thumbGen.emit()
			
    def run(self):
        for thumb, source in self.files.items():
            sourceDate = os.path.getmtime(source)
            if os.path.isfile(thumb):
                thumbDate = os.path.getmtime(thumb)
                if sourceDate > thumbDate:
                    self.generateThumb(source, thumb)
                else:
                    self.thumbGen.emit()
            else:
                self.generateThumb(source, thumb)
        self.finishGen.emit()

class GScene(QtGui.QGraphicsScene):
    def __init__(self):
        super(GScene, self).__init__()
        #Background Color
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(95, 95, 95)))
        #Context Menu
        self.menu = QtGui.QMenu()
        self.importAction = self.menu.addAction(QtGui.QIcon('%s/ImportFile.png' % mari_icon_path), 'Import Selected')
        self.copyAction = self.menu.addAction(QtGui.QIcon('%s/Copy.16x16.png' % mari_icon_path), 'Copy to Clipboard')

    def contextMenuEvent(self, event):
        self.menu.exec_(event.screenPos())

class GRectItem(QtGui.QGraphicsRectItem):
    def __init__(self, image_path, source):
        super(GRectItem, self).__init__()
        #Attributes
        self.setFlags(self.flags() | QtGui.QGraphicsItem.ItemIsSelectable)

        #Rect Settings
        self.setRect(0, 0, gViewItemSize, gViewItemSize)
        self.rectBrush = QtGui.QBrush(QtGui.QColor(100, 100, 100))
        self.rectPenBrush = QtGui.QBrush(QtGui.QColor(51, 51, 51))
        self.rectPen = QtGui.QPen(self.rectPenBrush, 1)
        self.setBrush(self.rectBrush)
        self.setPen(self.rectPen)

        #Pad Rect Settings
        self.setRect(0, 0, gViewItemSize, gViewItemSize)
        padRect = QtGui.QGraphicsRectItem()
        padRect.setPen(QtGui.QPen(self.rectPenBrush, 20))
        padRect.setParentItem(self)

        #Thumb Title Item
        thumbTitle = os.path.basename(source)
        if len(thumbTitle) >= 36:
            thumbTitle = thumbTitle[:34]+'...'
        self.setData(32, source)
        #Title Size Check
        self.thumbTitleItem = QtGui.QGraphicsSimpleTextItem(thumbTitle)
        self.thumbTitleItem.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 200)))
        self.thumbTitleItem.setPos(0, gViewItemSize)
        self.thumbTitleItem.setParentItem(self)

        #Thumb Image Item
        thumbImage = QtGui.QPixmap()
        #Cache thumbnail
        if not QtGui.QPixmapCache.find(image_path, thumbImage):
            thumbImage.load(image_path)
            QtGui.QPixmapCache.insert(image_path, thumbImage)
        else:
            QtGui.QPixmapCache.find(image_path, thumbImage)
        #Configure items with alphas
        if thumbImage.hasAlpha():
            backgroundImage = QtGui.QImage('%s/GrayChecker.png' % gViewIconDir)
            bgBrush = QtGui.QBrush(backgroundImage)
            self.setBrush(bgBrush)
        thumbImgItem = QtGui.QGraphicsPixmapItem(thumbImage)
        thumbWidth = thumbImgItem.pixmap().width()
        thumbHeight = thumbImgItem.pixmap().height()
        thumbHOffset = (gViewItemSize-thumbWidth)/2
        thumbVOffset = (gViewItemSize-thumbHeight)/2
        thumbImgItem.setPos(thumbHOffset, thumbVOffset)
        thumbImgItem.setParentItem(self)

    def itemChange(self, change, value):
        if change == QtGui.QGraphicsItem.ItemSelectedChange:
            if value == True:
                self.setHighlite()
            if value == False:
                self.removeHighlite()
        return QtGui.QGraphicsItem.itemChange(self, change, value)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            pass

    def setHighlite(self):
        highlitePenBrush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        highlitePen = QtGui.QPen(highlitePenBrush, 3)
        self.setPen(highlitePen)

    def removeHighlite(self):
        self.setPen(self.rectPen)

class GView(QtGui.QWidget):
    path = None
    maxColumns = 6
    vSceneSize = 0
    hSceneSize = 0
    items = 0
    def __init__(self):
        super(GView, self).__init__()

        mainLayout = QtGui.QVBoxLayout()
        self.viewSplitter = QtGui.QSplitter()
        toolLayout = QtGui.QHBoxLayout()
        progLayout = QtGui.QHBoxLayout()
        self.setLayout(mainLayout)

        self.gbook = GBookmark()
        self.gviewer = QtGui.QGraphicsView()
        self.gscene = GScene()
        self.gviewer.setInteractive(True)
        self.gviewer.setScene(self.gscene)
        self.gviewer.setAlignment( QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft )
        self.gviewer.resize(mari.app.canvasWidth() * 0.8, mari.app.canvasHeight())
        self.gbook.resize(mari.app.canvasWidth() * 0.2, mari.app.canvasHeight())

        self.pathLine = QtGui.QLineEdit()
        self.pathLabel = QtGui.QLabel('Path:')
        self.searchLine = QtGui.QLineEdit()
        self.searchLine.setMaximumWidth(200)
        self.searchLabel = QtGui.QLabel('Filter:')
        self.columnSpin = QtGui.QSpinBox()
        self.progBar1 = QtGui.QProgressBar()
        self.progLabel = QtGui.QLabel('Generating Thumbnails...')
        self.progStatus = QtGui.QLabel()
        self.progBar1.setHidden(True)
        self.progLabel.setHidden(True)
        self.progStatus.setHidden(True)
        self.browseBtn = QtGui.QPushButton('Browse')
        self.prefsBtn = QtGui.QToolButton()
        self.prefsBtn.setIcon(QtGui.QIcon('%s/ToolProperties.png' % mari_icon_path))
        self.prefsBtn.setToolTip('Set Thumbnail location')
        self.wizardBtn = QtGui.QToolButton()
        self.wizardBtn.setIcon(QtGui.QIcon('%s/MagicWand.png' % gViewIconDir))
        self.wizardBtn.setToolTip('Crawl Directories')
        self.addBookmarkBtn = QtGui.QToolButton()
        self.addBookmarkBtn.setIcon(QtGui.QIcon('%s/Star16x16.png' % gViewIconDir))
        self.addBookmarkBtn.setToolTip('Add bookmark for current path')
        self.loadBtn = QtGui.QToolButton()
        self.loadBtn.setIcon(QtGui.QIcon('%s/ReloadShaders.png' % mari_icon_path))
        self.loadBtn.setToolTip('Load path into viewer')
        self.fitBtn = QtGui.QToolButton()
        self.fitBtn.setIcon(QtGui.QIcon('%s/ABSSize.png' % mari_icon_path))
        self.fitBtn.setToolTip('Fit column width to view')
        self.statusBarLabel = QtGui.QLabel('Resolution:  Format:  Size:  Name:  ')
        self.statusBarLabel.setHidden(True)

        toolLayout.addWidget(self.prefsBtn)
        toolLayout.addWidget(self.wizardBtn)
        toolLayout.addWidget(self.searchLabel)
        toolLayout.addWidget(self.searchLine)
        toolLayout.addWidget(self.pathLabel)
        toolLayout.addWidget(self.pathLine)
        toolLayout.addWidget(self.browseBtn)
        toolLayout.addWidget(self.addBookmarkBtn)
        toolLayout.addWidget(self.loadBtn)

        self.viewSplitter.addWidget(self.gbook)
        self.viewSplitter.addWidget(self.gviewer)

        progLayout.addWidget(self.progLabel)
        progLayout.addWidget(self.progBar1)
        progLayout.addWidget(self.progStatus)
        progLayout.addWidget(self.statusBarLabel)
        progLayout.addStretch()
        progLayout.addWidget(self.columnSpin)
        progLayout.addWidget(self.fitBtn)

        mainLayout.addLayout(toolLayout)
        mainLayout.addWidget(self.viewSplitter)
        mainLayout.addLayout(progLayout)

        self.browseBtn.clicked.connect(self.browseCustomPath)
        self.loadBtn.clicked.connect(self.loadFromCustomPath)
        self.addBookmarkBtn.clicked.connect(self.setBookmark)
        self.fitBtn.clicked.connect(self.fitColumnsToCanvas)
        self.searchLine.textChanged.connect(self.sortItems)
        self.columnSpin.valueChanged.connect(self.setColumns)
        self.gscene.importAction.triggered.connect(self.importImages)
        self.gscene.copyAction.triggered.connect(self.copyPathToClipboard)
        self.gbook.itemSelectionChanged.connect(self.loadFromBookmark)
        self.prefsBtn.clicked.connect(self.setTempDir)
        self.wizardBtn.clicked.connect(self.setWizardBookmark)
        self.gbook.pathAdded.connect(self.crawlWizard)
        self.viewSplitter.splitterMoved.connect(self.fitColumnsToCanvas)
        self.gscene.selectionChanged.connect(self.updateStatusLabel)
        mari.utils.connect(mari.app.exiting, self.writePrefs)

        #Load bookmark Preferences
        try:
            self.gbook.buildTreeItems()
        except:
            print "gView Message: No prefs file found"

        self.viewSplitter.setSizes(gViewSizes)

    def updateStatusLabel(self):
        selectedItem = self.gscene.selectedItems()
        if selectedItem and len(selectedItem) == 1:
            source = selectedItem[0].data(32)
            reader = QtGui.QImageReader(source)
            name = os.path.basename(source)
            res = '%dx%d' % (reader.size().width(), reader.size().height())
            size = QtCore.QFileInfo(source).size() / 1024
            statusString = 'Name:  %s    Resolution:  %s    Size:  %s KB' % (name, res, size)
            self.statusBarLabel.setText(statusString)
            self.statusBarLabel.setHidden(False)
        else:
            self.statusBarLabel.setHidden(True)

    def getThumbnailPath(self, path):
        self.thumbnailPath = '%s/%s%s' % (gViewTempDir, gViewThumbDir, path)
        if mari.app.version().isWindows():
            cleanPath = path.replace(':','')
            self.thumbnailPath = os.path.join(gViewTempDir, gViewThumbDir, cleanPath)

    def buildPathDict(self, path):
		self.getThumbnailPath(path)
		if imagemagick_mode:
			supportedFormats = getImageMagicFormats()
		else:
			supportedFormats = QtGui.QImageWriter.supportedImageFormats()
		self.fileDict = {}
		dirList = os.listdir(path)
		
		for file in dirList:
			filePath = os.path.join(path, file)
			if os.path.isfile(filePath):
				#Build thumbnail directories
				if not os.path.exists(self.thumbnailPath):
					os.makedirs(self.thumbnailPath)
				#File paths
				thumbFile = '%s.%s' % (os.path.splitext(file)[0], 'png')
				thumbFile = os.path.join(self.thumbnailPath, thumbFile)
				#Format check:
				fileExtension = file.split(".")[-1]
				if fileExtension.lower() in supportedFormats:
					#Build file dict
					self.fileDict[thumbFile]=filePath

    def setBookmark(self):
        if not self.pathLine.text():
            return
        self.path = self.pathLine.text()
        self.gbook.buildFromPath(path=self.path, mode='single')

    def setWizardBookmark(self):
        path = QtGui.QFileDialog.getExistingDirectory(self, caption="Choose Texture Folder", options=QtGui.QFileDialog.ShowDirsOnly)
        self.gbook.buildFromPath(path, mode='multi')

    def loadFromBookmark(self):
        selectedItems = self.gbook.selectedItems()
        if len(selectedItems) > 1 or len(selectedItems) == 0:
            return
        self.path = selectedItems[0].data(0, 32)[3]
        self.pathLine.setText(self.path)
        if self.path:
            self.buildThumbnails()

    def loadFromCustomPath(self):
        self.path = self.pathLine.text()
        self.buildThumbnails()

    def buildThumbnails(self):
        self.buildPathDict(self.path)
        self.imageCount = len(self.fileDict)
        self.initProgBar()
        thumbnailThread = GThumbGen(self.fileDict)
        thumbnailThread.thumbGen.connect(self.thumbGenProgress)
        thumbnailThread.finishGen.connect(self.populateSceneTHREAD)
        thumbnailThread.run()

    def initProgBar(self):
        self.progBar1.setMaximum(self.imageCount)
        self.progBar1.setHidden(False)
        self.progLabel.setHidden(False)
        self.progStatus.setHidden(False)

    def thumbGenProgress(self):
        currentValue = self.progBar1.value()
        self.progBar1.setValue(currentValue+1)
        self.progStatus.setText('%s: %s/%s' % (os.path.basename(self.path), currentValue, self.imageCount))
        QtCore.QCoreApplication.processEvents()

    def populateSceneTHREAD(self):
        newThread = threading.Thread(target=self.populateScene())
        newThread.run()

    def populateScene(self):
        self.gscene.clear()
        self.setCursor(QtCore.Qt.BusyCursor)
        sortedFiles = sorted(self.fileDict.iteritems())

        for item in sortedFiles:
            thumb = item[0]
            source= item[1]
            bgRectItem = GRectItem(thumb, source)
            self.gscene.addItem(bgRectItem)
            self.items += 1
            self.setPositions(bgRectItem)
        self.progBar1.setHidden(True)
        self.progLabel.setHidden(True)
        self.progStatus.setHidden(True)
        self.unsetCursor()
        self.fitColumnsToCanvas()

    def setPositions(self, item):
        item.setPos(self.hSceneSize, self.vSceneSize)
        if self.items % self.maxColumns:
            self.hSceneSize += gViewItemSize+gViewItemVPad
        else:
            self.vSceneSize += gViewItemSize+gViewItemHPad
            self.hSceneSize = 0

    def setColumns(self):
        self.maxColumns = self.columnSpin.value()
        self.sortItems()

    def fitColumnsToCanvas(self):
        gbook_length = self.gbook.size().width()
        available_area = mari.app.canvasWidth() - gbook_length
        self.maxColumns = int(round(available_area / (gViewItemSize + gViewItemHPad)))
        self.columnSpin.setValue(self.maxColumns)
        self.sortItems()

    def sortItems(self):
        #Reset
        self.items = 0
        self.hSceneSize = 0
        self.vSceneSize = 0

        #List of Parent Items
        groupItems = []
        for item in self.gscene.items():
            if item.childItems():
                groupItems.append(item)
                item.setVisible(False)
                item.setPos(0,0)

        #Reverse Group List
        groupItems = groupItems[::-1]
        #Display Only Items Matching Search
        for item in groupItems:
            searchText = self.searchLine.text()
            titleItem = item.childItems()[1]
            thumbName = titleItem.text().split(".")[0]
            if searchText.lower() in thumbName.lower():
                item.setVisible(True)
                self.items += 1
                self.setPositions(item)

        #Resize Scene
        autoRect = self.gscene.itemsBoundingRect()
        self.gscene.setSceneRect(autoRect)
        ##Scroll to top
        self.gviewer.ensureVisible(0.0,0.0,0.0,0.0)

        #Refresh UI
        self.gscene.update()
        QtCore.QCoreApplication.processEvents()

    def setTempDir(self):
        global gViewTempDir
        directory = QtGui.QFileDialog.getExistingDirectory(self, caption="Choose Thumbnail Folder", dir=gViewTempDir, options=QtGui.QFileDialog.ShowDirsOnly)
        if directory:
            gViewTempDir = directory

    def browseCustomPath(self):
        directory = QtGui.QFileDialog.getExistingDirectory(self, caption="Choose Texture Folder", dir=self.path, options=QtGui.QFileDialog.ShowDirsOnly)
        if directory:
            self.pathLine.setText(directory)
            self.path = directory
            self.buildThumbnails()

    def writePrefs(self):
        configDict = {}
        configDict['gViewTempDir'] = gViewTempDir
        configDict['gViewSizes'] = self.viewSplitter.sizes()
        with open(gViewConfigFile, 'w') as outfile:
            json.dump(configDict, outfile)

        self.gbook.saveBookmarkFile()

    def importImages(self):
        selectedItems = self.gscene.selectedItems()
        for item in selectedItems:
            imagePath = item.data(32)
            print "Image Imported: ", imagePath
            mari.images.load(imagePath)

    def copyPathToClipboard(self):
        selectedItem = self.gscene.selectedItems()[-1]
        imagePath = selectedItem.data(32)
        QtGui.QClipboard().setText(imagePath, QtGui.QClipboard.Clipboard)

    def crawlWizard(self, path):
        self.path = path
        self.gbook.setDisabled(True)
        self.imageCount = 0

        #Find directories
        for root, dirs, files in os.walk(path, topdown=True):
            self.imageCount += len(files)

        #Make Thumbnails:
        self.buildPathDict(self.path)
        self.initProgBar()
        thumbnailThread = GThumbGen(self.fileDict)
        thumbnailThread.thumbGen.connect(self.thumbGenProgress)
        thumbnailThread.run()
        self.progBar1.setHidden(True)
        self.progLabel.setHidden(True)
        self.progStatus.setHidden(True)
        self.gbook.setDisabled(False)
