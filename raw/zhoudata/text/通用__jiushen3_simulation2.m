function threshold_simulation(B1_initial, B2_initial, B1_burst_initial, B2_burst_initial, second_part_duration)
    % 设置默认初始值
    if nargin < 5
        second_part_duration = 30; % 默认第二部分持续30秒
    end
    if nargin < 4
        B2_burst_initial = 0; % B2初始爆条帧数，默认为0
    end
    if nargin < 3
        B1_burst_initial = 0; % B1初始爆条帧数，默认为0
    end
    if nargin < 2
        B2_initial = 0; % B2初始X值，默认为0
    end
    if nargin < 1
        B1_initial = 0; % B1初始X值，默认为0
    end
    
    % 常量定义
    frame_rate = 30; % 帧率（帧/秒）
    part1_time = 30; % 第一部分持续时间（秒）
    total_time = part1_time + second_part_duration; % 总模拟时间（秒）
    total_frames = total_time * frame_rate; % 总帧数
    part1_burst_duration_frames = round((6 + 2/3) * frame_rate); % 第一部分爆条持续时间（帧）
    part2_burst_duration_frames = 10 * frame_rate; % 第二部分爆条持续时间（帧）
    
    % 初始化对象结构
    units = struct();
    units(1).name = 'A1';
    units(1).X = 0;
    units(1).burst = false;
    units(1).burst_remaining = 0;
    
    units(2).name = 'A2';
    units(2).X = 0;
    units(2).burst = false;
    units(2).burst_remaining = 0;
    
    units(3).name = 'B1';
    units(3).X = B1_initial;
    units(3).burst = (B1_burst_initial > 0);
    units(3).burst_remaining = B1_burst_initial;
    
    units(4).name = 'B2';
    units(4).X = B2_initial;
    units(4).burst = (B2_burst_initial > 0);
    units(4).burst_remaining = B2_burst_initial;
    
    % 初始化记录数组
    time_array = (0:total_frames-1) / frame_rate;
    X_history = zeros(4, total_frames);
    burst_history = false(4, total_frames);
    
    % 第一部分平A参数
    first_attack_frame = 7;
    attack_interval_frames = round((2 + 4/30) * frame_rate);
    
    % 第一部分全局增加参数
    first_global_frame = 10;
    global_interval_frames = 1 * frame_rate;
    
    % 第二部分平A参数
    part2_start_frame = part1_time * frame_rate;
    part2_first_attack_frame = part2_start_frame + 18;
    part2_attack_interval_frames = round((2 + 4/30) * frame_rate);
    
    % 主循环
    for frame = 1:total_frames
        % 检查是否进入第二部分
        if frame == part2_start_frame + 1
            % 调整爆条持续时间
            for i = 1:4
                if units(i).burst
                    % 剩余爆条时间乘以1.5倍，向下取整
                    units(i).burst_remaining = floor(units(i).burst_remaining * 1.5);
                end
            end
        end
        
        % 确定当前爆条持续时间
        if frame <= part2_start_frame
            current_burst_duration = part1_burst_duration_frames;
        else
            current_burst_duration = part2_burst_duration_frames;
        end
        
        % 更新爆条状态
        for i = 1:4
            if units(i).burst
                units(i).burst_remaining = units(i).burst_remaining - 1;
                if units(i).burst_remaining <= 0
                    units(i).burst = false;
                    units(i).X = 0;
                else
                    units(i).X = 0; % 爆条期间强制X为0
                end
            end
        end
        
        % 执行第一部分平A
        if frame <= part2_start_frame && frame >= first_attack_frame && mod(frame - first_attack_frame, attack_interval_frames) == 0
            % 选择目标（按优先级）
            target_idx = 0;
            for i = 1:4
                if ~units(i).burst
                    target_idx = i;
                    break;
                end
            end
            
            if target_idx > 0
                % 对目标增加X值
                units(target_idx).X = units(target_idx).X + 405.46;
                
                % 处理关联增加
                if target_idx == 1 % A1
                    if ~units(2).burst
                        units(2).X = units(2).X + 282.59;
                    end
                elseif target_idx == 3 % B1
                    if ~units(4).burst
                        units(4).X = units(4).X + 282.59;
                    end
                end
            end
        end
        
        % 执行第一部分全局增加
        if frame <= part2_start_frame && frame >= first_global_frame && mod(frame - first_global_frame, global_interval_frames) == 0
            for i = 1:4
                if ~units(i).burst
                    units(i).X = units(i).X + 122.86;
                end
            end
        end
        
        % 执行第二部分平A
        if frame > part2_start_frame && frame >= part2_first_attack_frame && mod(frame - part2_first_attack_frame, part2_attack_interval_frames) == 0
            % 选择目标（优先B1，如果B1爆条则选择B2）
            if ~units(3).burst % B1未爆条
                target_idx = 3;
                % B1增加115.84，B2增加80.74
                units(3).X = units(3).X + 115.84;
                if ~units(4).burst
                    units(4).X = units(4).X + 80.74;
                end
            else % B1爆条，选择B2
                target_idx = 4;
                % B2增加115.84
                units(4).X = units(4).X + 115.84;
            end
        end
        
        % 检查是否触发爆条
        for i = 1:4
            if units(i).X >= 1000 && ~units(i).burst
                units(i).burst = true;
                units(i).burst_remaining = current_burst_duration;
                units(i).X = 0;
            end
        end
        
        % 记录当前状态
        for i = 1:4
            X_history(i, frame) = units(i).X;
            burst_history(i, frame) = units(i).burst;
        end
    end
    
    % 绘制结果
    figure('Position', [100, 100, 1200, 800]);
    
    % X值随时间变化
    subplot(2, 1, 1);
    hold on;
    colors = ['r', 'g', 'b', 'm'];
    for i = 1:4
        plot(time_array, X_history(i, :), colors(i), 'DisplayName', units(i).name);
    end
    % 添加第一部分和第二部分的分隔线
    plot([part1_time, part1_time], ylim, 'k--', 'DisplayName', '第一部分结束');
    xlabel('时间 (秒)');
    ylabel('X值');
    title('单位X值随时间变化');
    legend;
    grid on;
    
    % 爆条状态随时间变化
    subplot(2, 1, 2);
    hold on;
    for i = 1:4
        % 将爆条状态转换为数值以便绘图
        burst_numeric = burst_history(i, :) * (i * 0.2 + 0.8);
        plot(time_array, burst_numeric, colors(i), 'DisplayName', units(i).name);
    end
    % 添加第一部分和第二部分的分隔线
    plot([part1_time, part1_time], ylim, 'k--', 'DisplayName', '第一部分结束');
    xlabel('时间 (秒)');
    ylabel('爆条状态 (偏移显示)');
    title('单位爆条状态随时间变化');
    legend;
    yticks(0.8:0.2:1.6);
    yticklabels({'否', 'A1', 'A2', 'B1', 'B2'});
    grid on;
    
    hold off;
end