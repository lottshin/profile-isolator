#Requires -Version 5.1
<#
.SYNOPSIS
  Codex Profile Isolator - graphical UI for CODEX_HOME multi-profile management.
#>

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Windows.Forms

$script:ToolDir = $PSScriptRoot
. (Join-Path $script:ToolDir 'cx-core.ps1')

# ---------------------------------------------------------------------------
# XAML
# ---------------------------------------------------------------------------

$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Codex Profile Isolator"
        Height="720" Width="1080"
        MinHeight="560" MinWidth="880"
        WindowStartupLocation="CenterScreen"
        Background="#0F1117"
        Foreground="#E6EAF2"
        FontFamily="Segoe UI"
        FontSize="13">
  <Window.Resources>
    <SolidColorBrush x:Key="Bg" Color="#0F1117"/>
    <SolidColorBrush x:Key="Panel" Color="#171A22"/>
    <SolidColorBrush x:Key="Panel2" Color="#1E2330"/>
    <SolidColorBrush x:Key="Border" Color="#2A3142"/>
    <SolidColorBrush x:Key="Text" Color="#E6EAF2"/>
    <SolidColorBrush x:Key="Muted" Color="#8B93A7"/>
    <SolidColorBrush x:Key="Accent" Color="#4C8DFF"/>
    <SolidColorBrush x:Key="Accent2" Color="#3D6FD9"/>
    <SolidColorBrush x:Key="Good" Color="#3DDC97"/>
    <SolidColorBrush x:Key="Warn" Color="#F0B429"/>
    <SolidColorBrush x:Key="Danger" Color="#FF6B6B"/>

    <Style TargetType="Button">
      <Setter Property="Background" Value="#1E2330"/>
      <Setter Property="Foreground" Value="#E6EAF2"/>
      <Setter Property="BorderBrush" Value="#2A3142"/>
      <Setter Property="BorderThickness" Value="1"/>
      <Setter Property="Padding" Value="12,7"/>
      <Setter Property="Margin" Value="0,0,8,0"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="bd"
                    Background="{TemplateBinding Background}"
                    BorderBrush="{TemplateBinding BorderBrush}"
                    BorderThickness="{TemplateBinding BorderThickness}"
                    CornerRadius="8"
                    Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="bd" Property="Background" Value="#2A3142"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Opacity" Value="0.45"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="PrimaryButton" TargetType="Button" BasedOn="{StaticResource {x:Type Button}}">
      <Setter Property="Background" Value="#4C8DFF"/>
      <Setter Property="Foreground" Value="White"/>
      <Setter Property="BorderBrush" Value="#4C8DFF"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="bd"
                    Background="{TemplateBinding Background}"
                    BorderBrush="{TemplateBinding BorderBrush}"
                    BorderThickness="1"
                    CornerRadius="8"
                    Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="bd" Property="Background" Value="#3D6FD9"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Opacity" Value="0.45"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="DangerButton" TargetType="Button" BasedOn="{StaticResource {x:Type Button}}">
      <Setter Property="Background" Value="#3A1F24"/>
      <Setter Property="BorderBrush" Value="#6B2C35"/>
      <Setter Property="Foreground" Value="#FFB4B4"/>
    </Style>

    <Style TargetType="TextBox">
      <Setter Property="Background" Value="#12151D"/>
      <Setter Property="Foreground" Value="#E6EAF2"/>
      <Setter Property="BorderBrush" Value="#2A3142"/>
      <Setter Property="BorderThickness" Value="1"/>
      <Setter Property="Padding" Value="10,8"/>
      <Setter Property="CaretBrush" Value="#E6EAF2"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="TextBox">
            <Border Background="{TemplateBinding Background}"
                    BorderBrush="{TemplateBinding BorderBrush}"
                    BorderThickness="{TemplateBinding BorderThickness}"
                    CornerRadius="8">
              <ScrollViewer x:Name="PART_ContentHost" Margin="{TemplateBinding Padding}"/>
            </Border>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style TargetType="ListBox">
      <Setter Property="Background" Value="Transparent"/>
      <Setter Property="BorderThickness" Value="0"/>
      <Setter Property="Padding" Value="0"/>
    </Style>

    <Style TargetType="ListBoxItem">
      <Setter Property="Padding" Value="0"/>
      <Setter Property="Margin" Value="0,0,0,8"/>
      <Setter Property="HorizontalContentAlignment" Value="Stretch"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ListBoxItem">
            <Border x:Name="bd" Background="#1E2330" CornerRadius="10" Padding="12,10" BorderBrush="#2A3142" BorderThickness="1">
              <ContentPresenter/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="bd" Property="Background" Value="#252B3A"/>
              </Trigger>
              <Trigger Property="IsSelected" Value="True">
                <Setter TargetName="bd" Property="Background" Value="#243356"/>
                <Setter TargetName="bd" Property="BorderBrush" Value="#4C8DFF"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style TargetType="TabControl">
      <Setter Property="Background" Value="Transparent"/>
      <Setter Property="BorderThickness" Value="0"/>
    </Style>
    <Style TargetType="TabItem">
      <Setter Property="Foreground" Value="#8B93A7"/>
      <Setter Property="Padding" Value="14,8"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="TabItem">
            <Border x:Name="bd" Background="Transparent" CornerRadius="8" Padding="{TemplateBinding Padding}" Margin="0,0,6,0">
              <ContentPresenter ContentSource="Header" HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsSelected" Value="True">
                <Setter TargetName="bd" Property="Background" Value="#1E2330"/>
                <Setter Property="Foreground" Value="#E6EAF2"/>
              </Trigger>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="bd" Property="Background" Value="#1A1F2B"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>

  <Grid Margin="16">
    <Grid.RowDefinitions>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="*"/>
      <RowDefinition Height="Auto"/>
    </Grid.RowDefinitions>

    <!-- Header -->
    <Grid Grid.Row="0" Margin="0,0,0,14">
      <Grid.ColumnDefinitions>
        <ColumnDefinition Width="*"/>
        <ColumnDefinition Width="Auto"/>
      </Grid.ColumnDefinitions>
      <StackPanel>
        <TextBlock Text="Codex Profile Isolator" FontSize="22" FontWeight="SemiBold"/>
        <TextBlock x:Name="TxtRoot" Text="Profiles root: -" Foreground="#8B93A7" Margin="0,4,0,0"/>
      </StackPanel>
      <StackPanel Grid.Column="1" Orientation="Horizontal" VerticalAlignment="Center">
        <Button x:Name="BtnRefresh" Content="Refresh"/>
        <Button x:Name="BtnOpenRoot" Content="Open Folder"/>
        <Button x:Name="BtnDoctor" Content="Doctor"/>
      </StackPanel>
    </Grid>

    <!-- Body -->
    <Grid Grid.Row="1">
      <Grid.ColumnDefinitions>
        <ColumnDefinition Width="320"/>
        <ColumnDefinition Width="14"/>
        <ColumnDefinition Width="*"/>
      </Grid.ColumnDefinitions>

      <!-- Left: profile list -->
      <Border Grid.Column="0" Background="#171A22" CornerRadius="14" Padding="12" BorderBrush="#2A3142" BorderThickness="1">
        <Grid>
          <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
          </Grid.RowDefinitions>

          <Grid Margin="0,0,0,10">
            <Grid.ColumnDefinitions>
              <ColumnDefinition Width="*"/>
              <ColumnDefinition Width="Auto"/>
            </Grid.ColumnDefinitions>
            <TextBlock Text="Profiles" FontSize="15" FontWeight="SemiBold" VerticalAlignment="Center"/>
            <TextBlock x:Name="TxtCount" Grid.Column="1" Text="0" Foreground="#8B93A7" VerticalAlignment="Center"/>
          </Grid>

          <ListBox x:Name="ListProfiles" Grid.Row="1">
            <ListBox.ItemTemplate>
              <DataTemplate>
                <Grid>
                  <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                  </Grid.ColumnDefinitions>
                  <StackPanel>
                    <TextBlock Text="{Binding Name}" FontWeight="SemiBold" FontSize="14"/>
                    <TextBlock Text="{Binding Model}" Foreground="#8B93A7" Margin="0,3,0,0"/>
                    <TextBlock Text="{Binding BaseUrl}" Foreground="#667085" FontSize="11" Margin="0,2,0,0" TextTrimming="CharacterEllipsis"/>
                  </StackPanel>
                  <Border Grid.Column="1" Background="#1A3A2A" CornerRadius="6" Padding="6,2" VerticalAlignment="Top"
                          Visibility="{Binding ActiveVisibility}">
                    <TextBlock Text="ACTIVE" Foreground="#3DDC97" FontSize="10" FontWeight="Bold"/>
                  </Border>
                </Grid>
              </DataTemplate>
            </ListBox.ItemTemplate>
          </ListBox>

          <StackPanel Grid.Row="2" Margin="0,12,0,0">
            <Button x:Name="BtnNew" Content="+ New Profile" Style="{StaticResource PrimaryButton}" HorizontalAlignment="Stretch" Margin="0,0,0,8"/>
            <Button x:Name="BtnImport" Content="Import from ~/.codex" HorizontalAlignment="Stretch" Margin="0"/>
          </StackPanel>
        </Grid>
      </Border>

      <!-- Right: details -->
      <Border Grid.Column="2" Background="#171A22" CornerRadius="14" Padding="16" BorderBrush="#2A3142" BorderThickness="1">
        <Grid>
          <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
          </Grid.RowDefinitions>

          <!-- Empty state -->
          <StackPanel x:Name="PanelEmpty" VerticalAlignment="Center" HorizontalAlignment="Center" Grid.RowSpan="4">
            <TextBlock Text="No profile selected" FontSize="18" FontWeight="SemiBold" HorizontalAlignment="Center"/>
            <TextBlock Text="Create one from current ~/.codex, or start from a blank template."
                       Foreground="#8B93A7" Margin="0,8,0,0" HorizontalAlignment="Center" TextWrapping="Wrap" TextAlignment="Center" MaxWidth="360"/>
          </StackPanel>

          <!-- Detail header -->
          <Grid x:Name="PanelDetail" Visibility="Collapsed">
            <Grid.ColumnDefinitions>
              <ColumnDefinition Width="*"/>
              <ColumnDefinition Width="Auto"/>
            </Grid.ColumnDefinitions>
            <StackPanel>
              <TextBlock x:Name="TxtName" Text="-" FontSize="20" FontWeight="SemiBold"/>
              <TextBlock x:Name="TxtPath" Text="-" Foreground="#8B93A7" Margin="0,4,0,0" TextTrimming="CharacterEllipsis"/>
            </StackPanel>
            <StackPanel Grid.Column="1" Orientation="Horizontal">
              <Button x:Name="BtnLaunch" Content="Launch Codex" Style="{StaticResource PrimaryButton}"/>
              <Button x:Name="BtnTerminal" Content="Open Terminal"/>
              <Button x:Name="BtnDelete" Content="Delete" Style="{StaticResource DangerButton}" Margin="0"/>
            </StackPanel>
          </Grid>

          <!-- Meta cards -->
          <Grid x:Name="PanelMeta" Grid.Row="1" Margin="0,14,0,12" Visibility="Collapsed">
            <Grid.ColumnDefinitions>
              <ColumnDefinition Width="*"/>
              <ColumnDefinition Width="10"/>
              <ColumnDefinition Width="*"/>
              <ColumnDefinition Width="10"/>
              <ColumnDefinition Width="*"/>
            </Grid.ColumnDefinitions>
            <Border Background="#1E2330" CornerRadius="10" Padding="12" BorderBrush="#2A3142" BorderThickness="1">
              <StackPanel>
                <TextBlock Text="MODEL" Foreground="#8B93A7" FontSize="11"/>
                <TextBlock x:Name="TxtModel" Text="-" FontWeight="SemiBold" Margin="0,4,0,0" TextWrapping="Wrap"/>
              </StackPanel>
            </Border>
            <Border Grid.Column="2" Background="#1E2330" CornerRadius="10" Padding="12" BorderBrush="#2A3142" BorderThickness="1">
              <StackPanel>
                <TextBlock Text="PROVIDER" Foreground="#8B93A7" FontSize="11"/>
                <TextBlock x:Name="TxtProvider" Text="-" FontWeight="SemiBold" Margin="0,4,0,0" TextWrapping="Wrap"/>
              </StackPanel>
            </Border>
            <Border Grid.Column="4" Background="#1E2330" CornerRadius="10" Padding="12" BorderBrush="#2A3142" BorderThickness="1">
              <StackPanel>
                <TextBlock Text="BASE URL" Foreground="#8B93A7" FontSize="11"/>
                <TextBlock x:Name="TxtBaseUrl" Text="-" FontWeight="SemiBold" Margin="0,4,0,0" TextWrapping="Wrap"/>
              </StackPanel>
            </Border>
          </Grid>

          <!-- Editor tabs -->
          <TabControl x:Name="Tabs" Grid.Row="2" Visibility="Collapsed">
            <TabItem Header="config.toml">
              <Grid Margin="0,10,0,0">
                <Grid.RowDefinitions>
                  <RowDefinition Height="*"/>
                  <RowDefinition Height="Auto"/>
                </Grid.RowDefinitions>
                <TextBox x:Name="EditorConfig" AcceptsReturn="True" AcceptsTab="True"
                         VerticalScrollBarVisibility="Auto" HorizontalScrollBarVisibility="Auto"
                         FontFamily="Consolas" FontSize="12" TextWrapping="NoWrap"/>
                <StackPanel Grid.Row="1" Orientation="Horizontal" Margin="0,10,0,0" HorizontalAlignment="Right">
                  <Button x:Name="BtnReloadConfig" Content="Reload"/>
                  <Button x:Name="BtnSaveConfig" Content="Save config.toml" Style="{StaticResource PrimaryButton}" Margin="0"/>
                </StackPanel>
              </Grid>
            </TabItem>
            <TabItem Header="auth.json">
              <Grid Margin="0,10,0,0">
                <Grid.RowDefinitions>
                  <RowDefinition Height="Auto"/>
                  <RowDefinition Height="*"/>
                  <RowDefinition Height="Auto"/>
                </Grid.RowDefinitions>
                <DockPanel Margin="0,0,0,8">
                  <CheckBox x:Name="ChkMaskKey" Content="Mask API key" Foreground="#8B93A7" IsChecked="True" VerticalAlignment="Center"/>
                </DockPanel>
                <TextBox x:Name="EditorAuth" Grid.Row="1" AcceptsReturn="True" AcceptsTab="True"
                         VerticalScrollBarVisibility="Auto" HorizontalScrollBarVisibility="Auto"
                         FontFamily="Consolas" FontSize="12" TextWrapping="NoWrap"/>
                <StackPanel Grid.Row="2" Orientation="Horizontal" Margin="0,10,0,0" HorizontalAlignment="Right">
                  <Button x:Name="BtnReloadAuth" Content="Reload"/>
                  <Button x:Name="BtnSaveAuth" Content="Save auth.json" Style="{StaticResource PrimaryButton}" Margin="0"/>
                </StackPanel>
              </Grid>
            </TabItem>
            <TabItem Header="Launch">
              <StackPanel Margin="0,14,0,0">
                <TextBlock Text="Working directory" Foreground="#8B93A7" Margin="0,0,0,6"/>
                <Grid>
                  <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                  </Grid.ColumnDefinitions>
                  <TextBox x:Name="TxtWorkDir"/>
                  <Button x:Name="BtnBrowseWorkDir" Grid.Column="1" Content="Browse" Margin="8,0,0,0"/>
                </Grid>
                <TextBlock Text="Extra codex args (optional)" Foreground="#8B93A7" Margin="0,14,0,6"/>
                <TextBox x:Name="TxtCodexArgs" ToolTip="e.g. resume"/>
                <TextBlock Text="Launch opens a new PowerShell window with CODEX_HOME set for this profile only. Other terminals are unaffected."
                           Foreground="#667085" TextWrapping="Wrap" Margin="0,14,0,0"/>
              </StackPanel>
            </TabItem>
          </TabControl>

          <!-- Status badges -->
          <StackPanel x:Name="PanelFlags" Grid.Row="3" Orientation="Horizontal" Margin="0,10,0,0" Visibility="Collapsed">
            <Border x:Name="BadgeConfig" Background="#1A3A2A" CornerRadius="6" Padding="8,4" Margin="0,0,8,0">
              <TextBlock x:Name="TxtBadgeConfig" Text="config: ok" Foreground="#3DDC97" FontSize="11"/>
            </Border>
            <Border x:Name="BadgeAuth" Background="#1A3A2A" CornerRadius="6" Padding="8,4" Margin="0,0,8,0">
              <TextBlock x:Name="TxtBadgeAuth" Text="auth: ok" Foreground="#3DDC97" FontSize="11"/>
            </Border>
            <Border x:Name="BadgeCatalog" Background="#3A2E14" CornerRadius="6" Padding="8,4" Visibility="Collapsed">
              <TextBlock Text="model_catalog_json present" Foreground="#F0B429" FontSize="11"/>
            </Border>
          </StackPanel>
        </Grid>
      </Border>
    </Grid>

    <!-- Footer -->
    <Grid Grid.Row="2" Margin="0,12,0,0">
      <Grid.ColumnDefinitions>
        <ColumnDefinition Width="*"/>
        <ColumnDefinition Width="Auto"/>
      </Grid.ColumnDefinitions>
      <TextBlock x:Name="TxtStatus" Text="Ready" Foreground="#8B93A7"/>
      <TextBlock Grid.Column="1" Text="CODEX_HOME isolation  ·  per-terminal providers" Foreground="#667085"/>
    </Grid>
  </Grid>
</Window>
'@

# ---------------------------------------------------------------------------
# Build window
# ---------------------------------------------------------------------------

$reader = New-Object System.Xml.XmlNodeReader ([xml]$xaml)
$window = [Windows.Markup.XamlReader]::Load($reader)

function Get-Ui([string]$Name) { $window.FindName($Name) }

$ListProfiles    = Get-Ui 'ListProfiles'
$TxtRoot         = Get-Ui 'TxtRoot'
$TxtCount        = Get-Ui 'TxtCount'
$TxtStatus       = Get-Ui 'TxtStatus'
$TxtName         = Get-Ui 'TxtName'
$TxtPath         = Get-Ui 'TxtPath'
$TxtModel        = Get-Ui 'TxtModel'
$TxtProvider     = Get-Ui 'TxtProvider'
$TxtBaseUrl      = Get-Ui 'TxtBaseUrl'
$PanelEmpty      = Get-Ui 'PanelEmpty'
$PanelDetail     = Get-Ui 'PanelDetail'
$PanelMeta       = Get-Ui 'PanelMeta'
$PanelFlags      = Get-Ui 'PanelFlags'
$Tabs            = Get-Ui 'Tabs'
$EditorConfig    = Get-Ui 'EditorConfig'
$EditorAuth      = Get-Ui 'EditorAuth'
$ChkMaskKey      = Get-Ui 'ChkMaskKey'
$TxtWorkDir      = Get-Ui 'TxtWorkDir'
$TxtCodexArgs    = Get-Ui 'TxtCodexArgs'
$TxtBadgeConfig  = Get-Ui 'TxtBadgeConfig'
$TxtBadgeAuth    = Get-Ui 'TxtBadgeAuth'
$BadgeConfig     = Get-Ui 'BadgeConfig'
$BadgeAuth       = Get-Ui 'BadgeAuth'
$BadgeCatalog    = Get-Ui 'BadgeCatalog'

$script:SelectedName = $null
$script:AuthRaw = ''
$script:LoadingEditor = $false

function Set-Status([string]$Message, [string]$Level = 'info') {
    $TxtStatus.Text = $Message
    switch ($Level) {
        'ok'    { $TxtStatus.Foreground = [Windows.Media.BrushConverter]::new().ConvertFromString('#3DDC97') }
        'warn'  { $TxtStatus.Foreground = [Windows.Media.BrushConverter]::new().ConvertFromString('#F0B429') }
        'error' { $TxtStatus.Foreground = [Windows.Media.BrushConverter]::new().ConvertFromString('#FF6B6B') }
        default { $TxtStatus.Foreground = [Windows.Media.BrushConverter]::new().ConvertFromString('#8B93A7') }
    }
}

function Show-UiError([string]$Message, [string]$Title = 'Error') {
    [System.Windows.MessageBox]::Show($Message, $Title, 'OK', 'Error') | Out-Null
    Set-Status $Message 'error'
}

function Confirm-Ui([string]$Message, [string]$Title = 'Confirm') {
    $r = [System.Windows.MessageBox]::Show($Message, $Title, 'YesNo', 'Question')
    return ($r -eq [System.Windows.MessageBoxResult]::Yes)
}

function Get-SelectedProfileName {
    $item = $ListProfiles.SelectedItem
    if (-not $item) { return $null }
    return [string]$item.Name
}

function Update-AuthEditor {
    $script:LoadingEditor = $true
    try {
        if ($ChkMaskKey.IsChecked) {
            $EditorAuth.Text = Mask-ApiKey $script:AuthRaw
            $EditorAuth.IsReadOnly = $true
        } else {
            $EditorAuth.Text = $script:AuthRaw
            $EditorAuth.IsReadOnly = $false
        }
    } finally {
        $script:LoadingEditor = $false
    }
}

function Load-ProfileDetail([string]$Name) {
    if (-not $Name) {
        $script:SelectedName = $null
        $PanelEmpty.Visibility = 'Visible'
        $PanelDetail.Visibility = 'Collapsed'
        $PanelMeta.Visibility = 'Collapsed'
        $PanelFlags.Visibility = 'Collapsed'
        $Tabs.Visibility = 'Collapsed'
        return
    }

    try {
        $path = Assert-ProfileExists $Name
        $s = Get-ConfigSummary $path
        $script:SelectedName = $Name

        $PanelEmpty.Visibility = 'Collapsed'
        $PanelDetail.Visibility = 'Visible'
        $PanelMeta.Visibility = 'Visible'
        $PanelFlags.Visibility = 'Visible'
        $Tabs.Visibility = 'Visible'

        $TxtName.Text = $Name
        $TxtPath.Text = $path
        $TxtModel.Text = $(if ($s.Model) { $s.Model } else { '(not set)' })
        $prov = @()
        if ($s.ProviderName) { $prov += $s.ProviderName }
        if ($s.Provider) { $prov += $s.Provider }
        $TxtProvider.Text = $(if ($prov.Count) { ($prov -join ' / ') } else { '(not set)' })
        $TxtBaseUrl.Text = $(if ($s.BaseUrl) { $s.BaseUrl } else { '(not set)' })

        if ($s.HasConfig) {
            $TxtBadgeConfig.Text = 'config: ok'
            $TxtBadgeConfig.Foreground = [Windows.Media.BrushConverter]::new().ConvertFromString('#3DDC97')
            $BadgeConfig.Background = [Windows.Media.BrushConverter]::new().ConvertFromString('#1A3A2A')
        } else {
            $TxtBadgeConfig.Text = 'config: missing'
            $TxtBadgeConfig.Foreground = [Windows.Media.BrushConverter]::new().ConvertFromString('#FF6B6B')
            $BadgeConfig.Background = [Windows.Media.BrushConverter]::new().ConvertFromString('#3A1F24')
        }

        if ($s.HasAuth) {
            $TxtBadgeAuth.Text = 'auth: ok'
            $TxtBadgeAuth.Foreground = [Windows.Media.BrushConverter]::new().ConvertFromString('#3DDC97')
            $BadgeAuth.Background = [Windows.Media.BrushConverter]::new().ConvertFromString('#1A3A2A')
        } else {
            $TxtBadgeAuth.Text = 'auth: missing'
            $TxtBadgeAuth.Foreground = [Windows.Media.BrushConverter]::new().ConvertFromString('#FF6B6B')
            $BadgeAuth.Background = [Windows.Media.BrushConverter]::new().ConvertFromString('#3A1F24')
        }

        $BadgeCatalog.Visibility = $(if ($s.HasCatalog) { 'Visible' } else { 'Collapsed' })

        $script:LoadingEditor = $true
        $EditorConfig.Text = Read-ProfileFile -Name $Name -Which config
        $script:AuthRaw = Read-ProfileFile -Name $Name -Which auth
        Update-AuthEditor
        $script:LoadingEditor = $false

        if (-not $TxtWorkDir.Text) {
            $TxtWorkDir.Text = Get-SafeLaunchDirectory
        }
    } catch {
        Show-UiError $_.Exception.Message
    }
}

function Refresh-ProfileList {
    param([string]$SelectName)

    try {
        [void](Initialize-CxRoot)
        $root = Get-CxRoot
        $TxtRoot.Text = "Profiles root: $root"

        $profiles = @(Get-CxProfiles)
        $items = foreach ($p in $profiles) {
            [pscustomobject]@{
                Name             = $p.Name
                Model            = $(if ($p.Model) { $p.Model } else { '(no model)' })
                BaseUrl          = $(if ($p.BaseUrl) { $p.BaseUrl } else { '' })
                Path             = $p.Path
                ActiveVisibility = $(if ($p.IsActive) { 'Visible' } else { 'Collapsed' })
            }
        }

        $ListProfiles.ItemsSource = $null
        $ListProfiles.ItemsSource = @($items)
        $TxtCount.Text = "$($items.Count)"

        if ($SelectName) {
            foreach ($it in $ListProfiles.Items) {
                if ($it.Name -eq $SelectName) {
                    $ListProfiles.SelectedItem = $it
                    break
                }
            }
        } elseif ($ListProfiles.Items.Count -gt 0 -and -not $ListProfiles.SelectedItem) {
            $ListProfiles.SelectedIndex = 0
        }

        if ($ListProfiles.Items.Count -eq 0) {
            Load-ProfileDetail $null
        }

        Set-Status "Loaded $($items.Count) profile(s)" 'ok'
    } catch {
        Show-UiError $_.Exception.Message
    }
}

function Show-NewProfileDialog {
    $dlgXaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="New Profile" Height="280" Width="460"
        WindowStartupLocation="CenterOwner"
        ResizeMode="NoResize"
        Background="#171A22" Foreground="#E6EAF2" FontFamily="Segoe UI" FontSize="13">
  <Grid Margin="18">
    <Grid.RowDefinitions>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="*"/>
      <RowDefinition Height="Auto"/>
    </Grid.RowDefinitions>
    <TextBlock Text="Create profile" FontSize="18" FontWeight="SemiBold"/>
    <StackPanel Grid.Row="1" Margin="0,16,0,0">
      <TextBlock Text="Name" Foreground="#8B93A7" Margin="0,0,0,6"/>
      <TextBox x:Name="NameBox" Padding="10,8"/>
    </StackPanel>
    <StackPanel Grid.Row="2" Margin="0,14,0,0">
      <CheckBox x:Name="FromCurrent" Content="Import from current ~/.codex" IsChecked="True" Foreground="#E6EAF2"/>
      <TextBlock Text="If unchecked, creates a blank template for you to fill in."
                 Foreground="#667085" TextWrapping="Wrap" Margin="0,8,0,0"/>
    </StackPanel>
    <StackPanel Grid.Row="4" Orientation="Horizontal" HorizontalAlignment="Right">
      <Button x:Name="CancelBtn" Content="Cancel" Width="90" Margin="0,0,8,0" IsCancel="True"/>
      <Button x:Name="OkBtn" Content="Create" Width="90" IsDefault="True"
              Background="#4C8DFF" Foreground="White" BorderBrush="#4C8DFF"/>
    </StackPanel>
  </Grid>
</Window>
'@
    $dlg = [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$dlgXaml)))
    $dlg.Owner = $window
    $nameBox = $dlg.FindName('NameBox')
    $fromCurrent = $dlg.FindName('FromCurrent')
    $ok = $dlg.FindName('OkBtn')
    $cancel = $dlg.FindName('CancelBtn')
    $result = @{ Ok = $false; Name = ''; FromCurrent = $true }

    $ok.Add_Click({
        if (-not $nameBox.Text.Trim()) {
            [System.Windows.MessageBox]::Show('Please enter a profile name.', 'New Profile') | Out-Null
            return
        }
        $result.Ok = $true
        $result.Name = $nameBox.Text.Trim()
        $result.FromCurrent = [bool]$fromCurrent.IsChecked
        $dlg.DialogResult = $true
        $dlg.Close()
    })
    $cancel.Add_Click({ $dlg.Close() })
    [void]$dlg.ShowDialog()
    return $result
}

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

$ListProfiles.Add_SelectionChanged({
    $name = Get-SelectedProfileName
    Load-ProfileDetail $name
})

(Get-Ui 'BtnRefresh').Add_Click({
    $cur = Get-SelectedProfileName
    Refresh-ProfileList -SelectName $cur
})

(Get-Ui 'BtnOpenRoot').Add_Click({
    try {
        $root = Initialize-CxRoot
        Start-Process explorer.exe $root
        Set-Status "Opened $root"
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnDoctor').Add_Click({
    try {
        $name = Get-SelectedProfileName
        $report = Get-CxDoctorReport -Name $name
        [System.Windows.MessageBox]::Show($report, 'cx doctor', 'OK', 'Information') | Out-Null
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnNew').Add_Click({
    try {
        $r = Show-NewProfileDialog
        if (-not $r.Ok) { return }
        $path = New-CxProfile -Name $r.Name -FromCurrent:$r.FromCurrent
        Refresh-ProfileList -SelectName $r.Name
        Set-Status "Created profile '$($r.Name)' at $path" 'ok'
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnImport').Add_Click({
    try {
        $defaultName = 'FromCurrent'
        $r = Show-NewProfileDialog
        if (-not $r.Ok) { return }
        $path = New-CxProfile -Name $r.Name -FromCurrent -Force:$false
        Refresh-ProfileList -SelectName $r.Name
        Set-Status "Imported ~/.codex into '$($r.Name)'" 'ok'
    } catch {
        # If exists, ask force
        if ($_.Exception.Message -match 'already exists') {
            if (Confirm-Ui "Profile already exists. Overwrite?" 'Import') {
                try {
                    $name = if ($r -and $r.Name) { $r.Name } else { $defaultName }
                    # re-show is awkward; parse from message or use last dialog name
                    # Use selected or prompt again - simpler: force with last name from exception path
                    $name = $r.Name
                    [void](New-CxProfile -Name $name -FromCurrent -Force)
                    Refresh-ProfileList -SelectName $name
                    Set-Status "Re-imported into '$name'" 'ok'
                } catch { Show-UiError $_.Exception.Message }
            }
        } else {
            Show-UiError $_.Exception.Message
        }
    }
})

(Get-Ui 'BtnDelete').Add_Click({
    try {
        $name = Get-SelectedProfileName
        if (-not $name) { return }
        if (-not (Confirm-Ui "Delete profile '$name'?`nThis removes its config.toml and auth.json." 'Delete profile')) { return }
        Remove-CxProfile -Name $name
        $script:SelectedName = $null
        Refresh-ProfileList
        Set-Status "Deleted profile '$name'" 'ok'
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnLaunch').Add_Click({
    try {
        $name = Get-SelectedProfileName
        if (-not $name) { return }
        $wd = $TxtWorkDir.Text
        $argsText = $TxtCodexArgs.Text
        $extra = @()
        if ($argsText -and $argsText.Trim()) {
            $extra = $argsText.Trim() -split '\s+'
        }
        Start-CxProfileSession -Name $name -WorkDir $wd -RunCodex -CodexArgs $extra
        Set-Status "Launched codex with profile '$name'" 'ok'
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnTerminal').Add_Click({
    try {
        $name = Get-SelectedProfileName
        if (-not $name) { return }
        Start-CxProfileSession -Name $name -WorkDir $TxtWorkDir.Text
        Set-Status "Opened terminal with profile '$name'" 'ok'
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnBrowseWorkDir').Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'Select working directory for codex'
    if ($TxtWorkDir.Text -and (Test-Path $TxtWorkDir.Text)) {
        $dlg.SelectedPath = $TxtWorkDir.Text
    }
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $TxtWorkDir.Text = $dlg.SelectedPath
    }
})

(Get-Ui 'BtnSaveConfig').Add_Click({
    try {
        $name = Get-SelectedProfileName
        if (-not $name) { return }
        [void](Save-ProfileFile -Name $name -Which config -Content $EditorConfig.Text)
        Load-ProfileDetail $name
        Refresh-ProfileList -SelectName $name
        Set-Status 'Saved config.toml' 'ok'
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnReloadConfig').Add_Click({
    try {
        $name = Get-SelectedProfileName
        if (-not $name) { return }
        $EditorConfig.Text = Read-ProfileFile -Name $name -Which config
        Set-Status 'Reloaded config.toml'
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnSaveAuth').Add_Click({
    try {
        $name = Get-SelectedProfileName
        if (-not $name) { return }
        if ($ChkMaskKey.IsChecked) {
            Show-UiError 'Uncheck "Mask API key" before editing/saving auth.json.'
            return
        }
        [void](Save-ProfileFile -Name $name -Which auth -Content $EditorAuth.Text)
        $script:AuthRaw = $EditorAuth.Text
        Load-ProfileDetail $name
        Set-Status 'Saved auth.json' 'ok'
    } catch { Show-UiError $_.Exception.Message }
})

(Get-Ui 'BtnReloadAuth').Add_Click({
    try {
        $name = Get-SelectedProfileName
        if (-not $name) { return }
        $script:AuthRaw = Read-ProfileFile -Name $name -Which auth
        Update-AuthEditor
        Set-Status 'Reloaded auth.json'
    } catch { Show-UiError $_.Exception.Message }
})

$ChkMaskKey.Add_Checked({ Update-AuthEditor })
$ChkMaskKey.Add_Unchecked({ Update-AuthEditor })

# ---------------------------------------------------------------------------
# Init + show
# ---------------------------------------------------------------------------

try {
    [void](Initialize-CxRoot)
    $TxtWorkDir.Text = Get-SafeLaunchDirectory
    Refresh-ProfileList
} catch {
    Set-Status $_.Exception.Message 'error'
}

[void]$window.ShowDialog()
